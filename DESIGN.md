# Design Note

**Framework: PydanticAI with Logfire.** Versatile and quick to set up; logging-first (every prompt, output and token cost is traced); and Pydantic schemas act as guardrails by validating each LLM decision.

## (a) System shape and key trade-offs

Code does what is checkable; an LLM does the judgment.

1. **Deterministic pass** (`mapper.py`): parses Notion page bodies (the CSVs drop the notes), normalizes dates, names and enums, applies knowledge-base rules, and lists *candidates* for the agent. Every source column has a recorded disposition (`field_map.py`); an unknown column stops the run.
2. **Agent** (`resolver.py`): per candidate it sees only the related CRM rows, notes, accounts and meetings, plus Slack and the KB, and chooses auto-apply, collapse duplicate, or flag, with confidence and provenance. An explicit matrix (`flag_matrix.py`) bounds it: flag an unknown or departed advisor, an unmatched account or meeting, a real contradiction, a stale valuation, an open question in a note; never flag what Slack settled, currency, or attribute differences kept in tags. A flag must carry a typed blocker (options, default, action applied).
3. **Assembly** (`assembler.py`): applies each blocker's default action, converts FX, asserts the 7 canonical rules, and fails if any held-out record lacks a blocker. Blockers are written to `outputs/blockers.md`.
4. **Memo** (`main.py`): blockers are grouped into one decision each, written for Dana, and fact-checked against the custodian feed.

**Trade-offs**
- LLM for judgment; code for arithmetic and invariants.
- No hardcoded answers: the memo can only contain what the blocker ledger contains.
- Output and memo share one `default_action`, so they cannot disagree.
- Flag only what Slack did not settle; dumping everything into flags is wrong (Rule 6).
- Live runs vary slightly; `--dry-run` replays `reference/llm_cache.json`.

## (b) Slack rules: encoding and correction

Each rule is a `KnowledgeRule` in `outputs/knowledge_base.json`, applied in Stage 1 before any LLM call.

| Dana's answer | Rule key | Effect |
|---|---|---|
| `Legacy` = acquired Harborline book | `status_map:Legacy` | ACTIVE + `lineage:harborline` |
| Advisor owns the relationship; Service Rep is paperwork; blank Advisor: don't guess | `ignored_field:Service Rep` | Never the advisor; household held out and asked |
| `A. Novak` left; surface her records | `departed_staff:A. Novak` | Not an advisor or attendee; tagged departed |
| AUM is market value; ignore cost basis | `ignored_field:Cost_Basis` | Dropped |
| Convert foreign balances to USD at quarter-end FX | `fx_rate:EUR`, `fx_rate:CHF` | Converted with provenance; never asked |
| Petrov is an import duplicate | `duplicate_client:Petrov, Dmitri` | Collapsed; meetings land on the survivor |
| Thompson left in 2023 | `status_map:Former`, `Churned` | INACTIVE |

**Correction.** Rules carry `version`, `active` and `evidence`. Changing a target bumps the version, and `active=false` retires a stale rule at once. Unanswered blockers are never learned as rules, and `llm` or `assumption` rules never settle a question the flag matrix still covers. Next: load Dana's Round 2 answers as `human` rules.
