# Design Note & Slack Rules Write-Up

Beaconcrest Advisors' Notion CRM, custodian positions, advisor roster and Round 1 Slack thread are mapped into the five Nevis entities. The mapping is half mechanical and half judgment: code does the mechanical part, an LLM makes the judgment calls, and only what a person must decide becomes a Round 2 question.

**Agent framework: PydanticAI with Logfire.** It is versatile and quick to set up, it is logging-first (Logfire traces every prompt, structured output and token cost out of the box), and Pydantic schemas double as guardrails by validating every LLM decision and retrying on a bad output.

## 1. Shape of the system

1. **Deterministic pass** (`mapper.py`): parses the Notion page bodies (the CSVs drop the notes), normalizes dates, names and enums, applies knowledge-base rules, and lists *candidate* cases (blank advisor, unmatched holder, stale date, note present...). Candidates are not flags.
2. **Agentic resolution** (`resolver.py`, `flag_matrix.py`): per candidate, the agent gets only its related CRM rows, notes, accounts and meetings plus the roster, Slack thread and KB, and decides `auto_apply`, `drop_duplicate` or `flag`, with confidence and provenance. The decision is bounded by an explicit matrix in its prompt: **flag** an unknowable/departed advisor (F1), unmatched holder (F2) or meeting (F3), a genuine source contradiction (F4), a stale valuation in an active household (F5), a low-confidence link (F6), an open question in a note (F7); **never flag** anything Slack settled, currency, or attribute differences kept in tags (D1-D10). A flag must carry a typed `Blocker`, enforced by a validator.
3. **Blocker ledger** (`blockers.py`): blockers are written to `outputs/blockers.md/.json`, grounded with custodian, amount and date from the feed.
4. **Assembly and validation** (`assembler.py`): builds the records, applies each blocker's `default_action` (hold out / retain and tag / set inactive), converts FX, asserts all 7 canonical rules, and fails if any held-out record lacks a blocker.
5. **Round 2 memo** (`main.py`): blockers are grouped into one decision each, written in Dana's language, and fact-checked against the custodian feed and the ledger (IDs, custodians, amounts, option and default consistency).

**Rule 6 and field coverage.** `field_map.py` records a disposition for every column of every source (map, normalize, preserve as `source_tags`, agent-read, or drop with a reason) and renders `outputs/field_dispositions.md`. A column with no entry stops the run, so a new field in a future sync cannot be silently ignored. For example, roster `office` has no home in the canonical advisor, so it is preserved as `office:<city>`; `Cost_Basis` and `Website` are dropped with reasons.

## 2. Key trade-offs

- **LLM for judgment, code for everything checkable**: dates, enums, FX, AUM sums and every invariant are deterministic.
- **No hardcoded answers**: no client or account is named in code; the memo can only contain what the ledger contains.
- **Memo and output cannot disagree**: one `default_action` drives both.
- **Under- vs over-flagging**: Rule 6 says dumping everything into flags is wrong, so settled items are never re-asked; unsettled ones are flagged.
- **Non-determinism**: a live re-run can flag slightly differently. `--dry-run` replays `reference/llm_cache.json`; the real LLM path is the default.

## 3. Slack rules and how they are encoded

Each rule is a `KnowledgeRule` in `outputs/knowledge_base.json`, keyed `<rule_type>:<source_value>`, applied in Stage 1 before any LLM call.

| Dana's answer | Rule | Effect |
|---|---|---|
| `Legacy` = acquired Harborline book; active, keep lineage | `status_map:Legacy` | ACTIVE + `lineage:harborline` |
| Advisor owns the relationship; Service Rep is paperwork; blank Advisor: don't guess, flag | `ignored_field:Service Rep` | Never the advisor; blank-Advisor households held out and asked (F1) |
| `A. Novak` left; surface records pointing at her | `departed_staff:A. Novak` | Not an advisor or attendee; tagged departed |
| AUM = market value at latest quarter-end; ignore cost basis | `ignored_field:Cost_Basis` | Dropped; AUM sums `market_value_usd` |
| Report in USD; convert foreign balances at quarter-end FX, note it | `fx_rate:EUR`, `fx_rate:CHF` | Converted automatically with provenance; never asked |
| `Dmitri Petrov` is an import duplicate; collapse | `duplicate_client:Petrov, Dmitri` | Row dropped; his meetings still land on the surviving household |
| Thompson left in 2023; inactive, not in active AUM | `status_map:Former/Churned` | INACTIVE |

**Applying and correcting.** Rules carry `version`, `active`, `scope` and `evidence`; `upsert()` bumps the version when a target changes and `active=false` retires a stale rule immediately. An unanswered blocker is never learned as a rule, and `llm`/`assumption` rules do not settle a case a flag rule still covers.

## 4. Next steps

- Load Dana's Round 2 answers as `human` rules (no answer-ingestion command yet).
- Add a regression set of expected flag / no-flag cases to pin down run-to-run variance.
