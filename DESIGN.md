# Design Note & Slack Rules Write-Up

Beaconcrest Advisors' Notion CRM, custodian positions, advisor roster and the Round 1 Slack thread are mapped into the five Nevis entities (`advisor`, `household`, `client`, `account`, `interaction`). The mapping is half mechanical and half judgment, so the pipeline automates what it can, lets an LLM make the judgment calls, and turns only what a person must decide into Round 2 questions.

## 1. Shape of the system

| Stage | Code | Job |
|---|---|---|
| 1. Deterministic pass | `src/mapper.py` | Parses the raw Notion page bodies (the CSVs drop the notes), normalizes dates, names and enums, applies knowledge-base rules, and emits *candidate* cases with reason codes (blank advisor, unmatched holder, stale date, critical tag, note present...). Candidates are not flags. |
| 2. Agentic resolution | `src/resolver.py`, `src/flag_matrix.py` | A PydanticAI agent (`gpt-5.6-luna`, traced with Logfire) gets one cross-source bundle per candidate (matching CRM rows and notes, custodian accounts, meetings) plus the roster, the Slack thread and the KB. It decides `auto_apply`, `drop_duplicate` or `flag_for_clarification`, with a confidence, provenance source and any reusable rule it learned. |
| 2b. Blocker ledger | `src/blockers.py` | Every flag carries a typed `Blocker` (matrix rule id, entities, evidence, options, default, `default_action`). They are written to `outputs/blockers.md` / `.json`, grounded with custodian, amount and date from the feed. |
| 3. Assembly + validation | `src/assembler.py` | Builds the canonical records, applies each blocker's `default_action` (`hold_out`, `retain_and_tag`, `set_inactive`), converts currency, and asserts all 7 canonical rules. Every held-out record must be explained by a blocker or the run fails. |
| 4. Round 2 memo | `main.py`, `src/blockers.py` | The memo is marked out of the ledger: blockers are grouped (same rule or shared account) into one decision each, the LLM writes it in Dana's language, and a data-driven fact-check verifies it. |

**The flag decision is the LLM's, bounded by an explicit matrix** (`src/flag_matrix.py`, rendered into the prompt):

- **Flag** when: F1 advisor missing or departed (never guess), F2 account holder unmatched, F3 meeting client unmatched, F4 sources genuinely contradict with no Slack answer, F5 stale valuation in an active household, F6 link still ambiguous (confidence < 0.80), F7 a page note states an open question.
- **Never flag** (D1-D10): Legacy, Service Rep, cost basis, any non-USD balance, Slack-confirmed duplicates, inactive households, confidently resolvable abbreviations and formats, spouse/co-client differences in Risk Profile or Fee Schedule and non-percentage fee labels (preserved in tags), irrelevant fields, and KB rules a human or Slack confirmed.

A validator rejects a flag without a blocker and a blocker on a never-flag case, so the matrix is enforced in code, not just requested.

## 2. Key trade-offs

- **LLM where judgment is needed, code where it is better.** Matching, ambiguity and wording go to the model. Dates, enums, FX arithmetic, AUM sums, holdout coverage and every invariant stay deterministic.
- **Per-case context, not one giant prompt.** Each case gets only its related records, so decisions are traceable and cheap to retry.
- **No hardcoded answers.** Nothing in the code names a client or account. The memo can only contain what the ledger contains, and the fact-check derives its expectations from the custodian feed and the ledger.
- **Memo and output cannot disagree.** The same `default_action` drives the canonical output and the memo's proposed default, and a check confirms the default's wording reflects the applied action.
- **Under-flag vs over-flag.** Rule 6 says dumping everything into flags is wrong, so settled items are never re-asked. When Slack does not settle something, the agent flags it.
- **Structured-output retries.** The agents retry up to 4 times to repair schema misses. The model is non-deterministic, so a re-run can flag slightly differently; the committed outputs are one live run.
- **Offline fallback.** `--dry-run` replays `reference/llm_cache.json` so the pipeline can be checked without a key. The real LLM path is the default.

## 3. Normalization and Rule 6

- **Dates** to ISO `YYYY-MM-DD`. **Names**: inverted `Last, First` is split. **Households** strip a trailing "Household" and get stable ids (`hh_chen`).
- **Enums**: status (`Active`/`Client` to ACTIVE, `Former`/`Churned` to INACTIVE, `Legacy` to ACTIVE plus a lineage tag), account type (`Joint WROS`/`TIC` to JOINT, `Rollover IRA` to IRA, `Trust-Rev` to TRUST), interaction type (`QBR`/`Check-in`/`Annual Review` to REVIEW, `Intro Call`/`Discovery` to PROSPECTING).
- **Currency**: non-USD balances convert to `market_value_usd` at the 2025-06-30 quarter-end ECB rates (EUR 1.1720, CHF 1.2539 USD per unit), keep `currency_original`, and record rate and source in provenance.
- **Preserved in `source_tags`**: segment, risk profile, fee schedule, client-since, referred-by, tags (VIP, ESG, Do Not Contact), `lineage:harborline`, and `service_rep:<name>` (never the primary advisor).
- **Dropped with a logged reason**: `Cost_Basis` (tax only, per Dana), `Website`, roster `office`.
- **Provenance** on every value: `deterministic`, `slack_knowledge`, `llm`, `assumption` (or `human`).

## 4. Rules from the Slack thread and how they are encoded

Each rule is a `KnowledgeRule` in `outputs/knowledge_base.json`, keyed `<rule_type>:<source_value>`, applied by Stage 1 before any LLM call.

| What Dana said | Rule key | Effect |
|---|---|---|
| `Legacy` = the acquired Harborline book; treat as active, keep the lineage | `status_map:Legacy` | ACTIVE plus tag `lineage:harborline` |
| Advisor owns the relationship; Service Rep is paperwork only; blank Advisor: don't guess, flag it | `ignored_field:Service Rep` | Never maps to `primary_advisor_id`; those households are held out and asked in Round 2 (F1) |
| `A. Novak` is Anna Novak, a contractor who left; surface anything still pointing at her | `departed_staff:A. Novak` | Not accepted as an advisor or attendee; affected records flagged |
| AUM is market value at the most recent quarter-end; ignore cost basis | `ignored_field:Cost_Basis` | Dropped; `aum_usd` is the sum of `market_value_usd` |
| Report in USD, convert foreign balances at quarter-end FX and note it | `fx_rate:EUR` (and `fx_rate:CHF`, same policy) | Converted automatically with provenance; never flagged (D4) |
| `Dmitri Petrov` is an import duplicate; collapse | `duplicate_client:Petrov, Dmitri` | Duplicate row dropped; its name still resolves to the surviving household, so his meeting lands |
| Thompson left in 2023, winding down; mark inactive, exclude from active AUM | `status_map:Former`, `status_map:Churned` | INACTIVE |

**Applying and correcting rules.** Stage 1 looks a rule up before creating a candidate, so a warm KB removes already-settled cases from the LLM's queue. Rules carry `version`, `active`, `scope` (`firm_specific` or `global_reusable`) and `evidence`. `upsert()` bumps the version when a target changes, and `active=false` retires a stale rule at once. Safeguards against a wrong rule going stale: the agent never learns a rule from a record it flagged (an unanswered question is not an answer), and KB rules with provenance `llm` or `assumption` do not settle a case that a flag rule still covers.

## 5. Known gaps and next steps

- Dana's Round 2 answers are applied by upserting rules with provenance `human`; there is no answer-ingestion command yet.
- The flag decision varies a little between live runs; a regression set of expected flag/no-flag cases would pin it down.
