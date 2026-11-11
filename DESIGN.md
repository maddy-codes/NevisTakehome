# Nevis Onboarding Pipeline — Design & Rules Write-Up

## 1. System Architecture & Key Trade-Offs

The pipeline maps Beaconcrest Advisors' Notion CRM (`Clients*.md`, `Meetings*.md`), custodian balances (`custodian_positions.xlsx`), advisor roster (`advisor_roster.csv`), and Round 1 onboarding Slack thread (`ops_slack_thread.md`) into the five Nevis canonical entities (`advisor`, `household`, `client`, `account`, `interaction`) across four observable stages:

1. **Stage 1 — Deterministic & Knowledge-Base Pass (`mapper.py`)**:
   - Parses the raw Notion Markdown folders (rather than relying solely on the CSVs, which drop the unstructured page body notes) and aligns exact matches, standard dates (`YYYY-MM-DD`), and unambiguous enums (`Individual -> INDIVIDUAL`, `Roth IRA -> ROTH_IRA`, etc.).
   - Consults `knowledge_base.json` before flagging any record. Rules learned from prior runs or stakeholder answers are applied deterministically (`source="slack_knowledge"` or `"llm"`) without redundant LLM calls.
   - Records with non-standard enums (`Legacy`, `Former`, `Churned`, `Client`), missing/abbreviated advisors (`P. Raman`, `E. Sokolova`, `A. Novak`), unstructured notes, non-USD currencies (`EUR`, `CHF`), stale `As_Of_Date` values, failed exact entity joins (`Bob & Linda Chen`, `Ada Okonkwo Revocable Trust`, `Nakamura Holdings LLC`), or critical compliance tags (`Deceased`, `Held Away`) are emitted as `UnresolvedCase` objects with explicit reason codes.

2. **Stage 2 — Context-Targeted Agentic Resolution (`resolver.py`)**:
   - Built with **PydanticAI** (`openai:gpt-5.6-luna`) and instrumented end-to-end with **Pydantic Logfire** (`logfire.instrument_pydantic_ai()`) so every batch, prompt, structured output, and token cost is traced.
   - **Why PydanticAI + Logfire**: Enforces strict Pydantic schema validation (`BatchResolutionOutput`) on LLM decisions while giving full OpenTelemetry trace visibility across deterministic and agentic spans.
   - Instead of one giant prompt, `build_case_context()` constructs a targeted cross-source bundle per `UnresolvedCase` (matching CRM records + Markdown notes + custodian accounts + meetings) alongside the Advisor Roster and Round 1 Slack thread.
   - Each resolution emits a confidence score (`0.0–1.0`), provenance, and reusable `KnowledgeRule` items persisted to `knowledge_base.json`.

3. **Stage 3 — Canonical Assembly & Post-Mapping Validation (`assembler.py`)**:
   - Enforces all 7 Nevis Canonical Rules: holds out households missing a `primary_advisor_id` (Rule 1), sums `market_value_usd` per household (Rule 2), sets `aum_usd = null` (never `0`) when a household has no known accounts (Rule 3), blocks orphan accounts (Rule 4) and orphan interactions (Rule 7) from landing in `canonical_output.json`, and converts non-USD balances while preserving `currency_original` (Rule 5).
   - **Rule 6 (Fields with no first-class home)**:
     - *Preserved & normalized in `source_tags`*: `Segment` (`High Net Worth -> segment:HNW`), `Risk Profile` (`3 - Moderate -> risk_profile:Moderate`), `Fee Schedule` (`tier 1 -> fee_schedule:Tier 1`), `Client Since` (`client_since:YYYY-MM-DD`), `Referred By`, `Tags` (`VIP`, `ESG`, `Do Not Contact`), and `Legacy -> lineage:harborline`.
     - *Dropped with logged rationale*: `custodian_positions.Cost_Basis` (per Dana in Slack: tax-only), `clients.Website` (irrelevant to wealth management canonical model), `clients.Service Rep` (administrative role, never used as `primary_advisor_id`), and `advisor_roster.office` (not in canonical `advisor` schema).
   - **Post-Mapping Validator**: Detects cross-record contradictions across multi-member households (spouses in `Chen`, `Abramson`, `Sullivan`, and `Thompson` having conflicting `Risk Profile` and `Fee Schedule` values) and asserts all 7 canonical invariants.

4. **Stage 4 — Round 2 Clarification Synthesizer (`main.py`)**:
   - Deduplicates and groups raw flags into `clarifications_round2.md` for Dana Ruiz, with **Trigger**, **Evidence**, **Candidate Options**, and **Proposed Default** per question, strictly filtering out anything settled in Round 1.

---

## 2. Business Rules Extracted from `sources/ops_slack_thread.md` & Lifecycle in `knowledge_base.json`

| Slack Rule (Dana Ruiz, Round 1) | Encoded `KnowledgeRule` Key in `knowledge_base.json` | Canonical Action |
|---|---|---|
| `Status = Legacy` is the 2019 Harborline acquisition book; treat as active clients and keep lineage | `status_map:Legacy` (`scope="firm_specific"`) | `status = ACTIVE` + append `"lineage:harborline"` to `source_tags` |
| `Advisor` owns the relationship; `Service Rep` is paperwork only — never fall back to `Service Rep` when `Advisor` is blank | `ignored_field:Service Rep` | Do not map `Service Rep` to `primary_advisor_id`; flag blank `Advisor` households (`Delgado`, `Whitfield`, `Petit`, `Vandermeer`) to Dana |
| `A. Novak` (Anna Novak) is a contractor who left last year; surface records still pointing to her | `departed_staff:A. Novak` | Clear `A. Novak` from meeting `Attendee` (`Review — Delgado`) and flag `George Whitfield` / `Maria Delgado` for reassignment |
| AUM is always `Market_Value` as of quarter-end; ignore `Cost_Basis` | `ignored_field:Cost_Basis` | Drop `Cost_Basis`; compute `aum_usd` from `market_value_usd` |
| Report everything in USD; convert `EUR` (`Al-Rashid`) using quarter-end FX rate and note conversion | `fx_rate:EUR` (`1.08`), `fx_rate:CHF` (`1.12`) | Convert to `market_value_usd`, preserve `currency_original`, record FX provenance (and confirm `CHF` with Dana) |
| `Dmitri Petrov` / `Petrov, Dmitri` is an import duplicate — collapse into one person | `duplicate_client:Petrov, Dmitri`, `meeting_client_alias:Petrov, Dmitri` | Drop duplicate client row, route meeting to `Petrov Household`, flag conflicting Fee/Risk values (`1.10%/Moderate` vs `1.00%/Aggressive`) |
| `Thompson` household (`Former` / `Churned`) left in 2023 and is winding down | `status_map:Former`, `status_map:Churned` | Map `Thompson Household` to `status = INACTIVE` |

### How Rules Auto-Apply on Next Sync & Get Corrected When Stale
- Every rule in [`knowledge_base.json`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/knowledge_base.json) is keyed deterministically by `<rule_type>:<source_value>` with `version`, `active`, `scope` (`firm_specific` vs `global_reusable`), and `evidence`.
- On subsequent syncs, Stage 1 (`mapper.py`) queries `kb.get_rule(rule_type, source_value)` before creating an `UnresolvedCase`. On Sync #1 (cold start), 40 records require LLM resolution; on Sync #2 (warm `knowledge_base.json`), **26 rules auto-apply in Stage 1**, cutting unresolved LLM cases from 40 down to the 21 genuinely ambiguous records awaiting Dana's Round 2 answers.
- When a rule changes or is corrected by Dana in Round 2, `kb.upsert()` overwrites `<rule_type>:<source_value>`, increments `version`, and logs the transition in Logfire (`active=False` disables a stale rule immediately).

