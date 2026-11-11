# Nevis Onboarding Pipeline — Design & Rules Write-Up

## 1. System Architecture & Key Trade-Offs

The pipeline maps Beaconcrest Advisors' Notion CRM (`Clients*.md`, `Meetings*.md`), custodian balances (`custodian_positions.xlsx`), advisor roster (`advisor_roster.csv`), and Round 1 onboarding Slack thread (`ops_slack_thread.md`) into the five Nevis canonical entities (`advisor`, `household`, `client`, `account`, `interaction`) across four observable stages:

1. **Stage 1 — Deterministic & Knowledge-Base Pass (`src/mapper.py`)**:
   - Parses the raw Notion Markdown folders (rather than relying solely on the CSVs, which drop the unstructured page body notes) and aligns exact matches, standard dates (`YYYY-MM-DD`), and unambiguous enums (`Individual -> INDIVIDUAL`, `Roth IRA -> ROTH_IRA`, etc.).
   - Consults `outputs/knowledge_base.json` before flagging any record. Rules learned from prior runs or stakeholder answers are applied deterministically (`source="slack_knowledge"` or `"llm"`) without redundant LLM calls.
   - Records with non-standard enums (`Legacy`, `Former`, `Churned`, `Client`), missing/abbreviated advisors (`P. Raman`, `E. Sokolova`, `A. Novak`), unstructured notes, non-USD currencies (`EUR`, `CHF`), stale `As_Of_Date` values, failed exact entity joins (`Bob & Linda Chen`, `Ada Okonkwo Revocable Trust`, `Nakamura Holdings LLC`), or critical compliance tags (`Deceased`, `Held Away`) are emitted as `UnresolvedCase` objects with explicit reason codes.

2. **Stage 2 — Context-Targeted Agentic Resolution (`src/resolver.py`)**:
   - Built with **PydanticAI** (`openai:gpt-5.6-luna`) and instrumented end-to-end with **Pydantic Logfire** (`logfire.instrument_pydantic_ai()`) so every batch, prompt, structured output, and token cost is traced.
   - **Why PydanticAI + Logfire**: Enforces strict Pydantic schema validation (`BatchResolutionOutput`) on LLM decisions while giving full OpenTelemetry trace visibility across deterministic and agentic spans. Includes disk caching (`reference/llm_cache.json`) for deterministic, offline reproducibility without an API key.
   - Instead of one giant prompt, `build_case_context()` constructs a targeted cross-source bundle per `UnresolvedCase` (matching CRM records + Markdown notes + custodian accounts + meetings) alongside the Advisor Roster and Round 1 Slack thread.
   - Each resolution emits a confidence score (`0.0–1.0`), strict provenance attribution, and reusable `KnowledgeRule` items persisted to `outputs/knowledge_base.json`.

3. **Stage 3 — Canonical Assembly & Post-Mapping Validation (`src/assembler.py`)**:
   - Enforces all 7 Nevis Canonical Rules: holds out households missing a `primary_advisor_id` (Rule 1), sums `market_value_usd` per household (Rule 2), sets `aum_usd = null` (never `0`) when a household has no known accounts (Rule 3), blocks orphan accounts (Rule 4) and orphan interactions (Rule 7) from landing in `outputs/canonical_output.json`, and converts non-USD balances with cited central bank FX rates while recording rule ID, rate, and source in provenance (Rule 5).
   - **Rule 6 (Fields with no first-class home)**:
     - *Preserved & normalized in `source_tags`*: `Segment` (`High Net Worth -> segment:HNW`), `Risk Profile` (`3 - Moderate -> risk_profile:Moderate`), `Fee Schedule` (`tier 1 -> fee_schedule:Tier 1`), `Client Since` (`client_since:YYYY-MM-DD`), `Referred By`, `Tags` (`VIP`, `ESG`, `Do Not Contact`), `Legacy -> lineage:harborline`, and `Service Rep` (`service_rep:<name>` / `service_rep:A. Novak (departed)`).
     - *Dropped with logged rationale*: `custodian_positions.Cost_Basis` (per Dana in Slack: tax-only), `clients.Website` (synthetic URLs, irrelevant to wealth management canonical model), and `advisor_roster.office` (not in canonical `advisor` schema).
   - **Consistency with Clarifications**: Proposed defaults match canonical output exactly:
     - Omar Farouk defaulted to `INACTIVE` with `pending:round2_deceased_status`.
     - Kenji Nakamura's IRA held in unassigned onboarding queue pending family confirmation (`pending:round2_householding`).
     - Stale active accounts (Ashford `CU-6024`, Delgado `CU-5004`) retained with historical dates tagged `pending:round2_stale_valuation`.
     - Unmatched custodian accounts (`CU-5010`, `CU-6025`) and Redwood Capital interaction held in onboarding/prospect queues without creating orphan records.
   - **Post-Mapping Validator**: Asserts all 7 canonical invariants hold on `outputs/canonical_output.json`. Spouses maintain their individual `risk_profile` and `fee_schedule` tags on their respective `Client` records without inventing artificial household-level conflicts.

4. **Stage 4 — Round 2 Clarification Synthesizer & Post-Synthesis Fact-Check Validator (`main.py`, `src/assembler.py`)**:
   - Synthesizes an executive, 8-decision operational memorandum for Dana Ruiz in `outputs/clarifications_round2.md`.
   - Adheres strictly to wealth management business language (zero database/engineering jargon; no email roleplay or conversational filler).
   - Formulates the 8 operational decisions with verified ground-truth facts:
     1. Primary Advisor assignments for Delgado, Whitfield, Petit, Vandermeer (Dana: *"Don't guess. Flag those to me and I'll tell you the right advisor"*).
     2. Stale account valuations for Delgado (`CU-5004` at Schwab, $1.24M, 2024-12-31) and Ashford (`CU-6024` at Fidelity, $1.45M, 2024-09-30).
     3. Deceased primary contact vs active status for Omar Farouk (`CU-6035` at Schwab, $1.66M, 2025-06-30).
     4. Holding structure for Kenji Nakamura IRA (`CU-5011` at Fidelity, $210k) vs Nakamura Holdings LLC (`CU-5006` at Fidelity, $8.9M).
     5. Unmatched custodian accounts for Carlos Vasquez (`CU-5010` at Schwab, $980k) and Priyanka Mehta (`CU-6025` at Schwab, $670k).
     6. Orphan prospect interaction for Redwood Capital introductory meeting on June 8, 2025 (`"Referred lead — not in the CRM yet"`).
     7. Swiss Franc (CHF) exchange rate confirmation for Francesca Bianchi (`CU-6022` at Pictet, 2.1M CHF at 1.2539 USD/CHF).
     8. Conflicting spouse profile attributes (Chen, Abramson, Sullivan, Thompson) and undefined fee tiers (Tier 1, Tier 2, See LOE).
   - **Automated Post-Synthesis Fact-Check Validator (`verify_clarifications_fact_check`)**:
     Extracts every account ID, holder, custodian, amount, and date from the generated memorandum and validates them against `custodian_positions.xlsx`. Rigorously asserts zero hallucinated phrases (such as fabricated CPAs or invented "transition spreadsheets"), verifies option-to-default alignment, and fails if any anomaly or discrepancy is detected.

---

## 2. Comprehensive Data Normalization Architecture

The pipeline implements a 4-tier normalization pipeline that systematically cleans and maps unstructured client CRM records:

### A. Format & Type Normalization
1. **Dates**: Notion CRM exports dates as mixed human prose (`"June 12, 2025"`, `"September 5, 2023"`, `"November 2, 2019"`), while custodian spreadsheets use standard date formats. The parser normalizes all date occurrences across `Client Since`, `Date`, and `As_Of_Date` using `pd.to_datetime(..., format="mixed").dt.strftime("%Y-%m-%d")` into strict ISO-8601 `YYYY-MM-DD`.
2. **Person Names**: Inverted CSV export artifacts (`"Petrov, Dmitri"`, `"Nakamura, Kenji"`) are detected via comma presence, extracting `first_name="Dmitri"`, `last_name="Petrov"`. Standard strings (`"First Last"`) split cleanly on trailing whitespace.
3. **Household Entities**: Raw CRM household names vary from single family names (`"Okonkwo"`), to compound phrases (`"Chen Household"`), to empty fields. The pipeline strips trailing whitespace and redundant `" Household"` substrings using regex (`r"\s+Household$"`), generating canonical names (`"Chen Household"`) and deterministic URL-safe primary keys (`hh_chen`, `hh_okonkwo`).

### B. Enum & Semantic Normalization
1. **Status Mapping (`ACTIVE | INACTIVE | PROSPECT`)**:
   - Standard active variants (`'Active'`, `'active '`, `'ACTIVE'`, `'Client'`) map to `ACTIVE`.
   - The knowledge layer maps `'Legacy'` to `ACTIVE` while attaching `"lineage:harborline"` to `source_tags`, honoring Dana's requirement to track the acquired book.
   - Winding-down and departed clients (`'Former'`, `'Churned'`) map to `INACTIVE`.
   - Onboarding leads (`'Prospect'`) map to `PROSPECT`.
2. **Account Types (`INDIVIDUAL | JOINT | TRUST | IRA | ROTH_IRA | CORPORATE | OTHER`)**:
   - Normalizes custodian terms: `'Joint WROS'` / `'Joint TIC'` → `JOINT`; `'Rollover IRA'` → `IRA`; `'Trust-Rev'` → `TRUST`; `'Corporate'` → `CORPORATE`.
3. **Interaction Types (`REVIEW | PROSPECTING | ONBOARDING | OTHER`)**:
   - Normalizes meeting labels: `'Annual Review'`, `'Review'`, `'QBR'`, `'Check-in'` → `REVIEW`; `'Intro Call'`, `'Discovery'`, `'Prospecting'` → `PROSPECTING`; `'Onboarding'` → `ONBOARDING`.

### C. Rule 6: Normalizing Fields with No First-Class Home
Because the target schema deliberately limits first-class columns to universal core attributes, custom Notion CRM fields are preserved as normalized, structured strings inside `source_tags`:
- `Segment`: Standardized uppercase notation (`"High Net Worth"` → `segment:HNW`, `segment:Mass Affluent`, `segment:Corporate`).
- `Risk Profile`: Scale syntax normalized (`"3 - Moderate"` → `risk_profile:Moderate`, `risk_profile:Conservative`, `risk_profile:Aggressive`, `risk_profile:Growth`).
- `Fee Schedule`: Normalized casing (`"tier 1"` → `fee_schedule:Tier 1`, `fee_schedule:1.00%`, `fee_schedule:0.85%`).
- `Lineage & Attribution`: `referred_by:<source>`, `client_since:YYYY-MM-DD`, `tag:VIP`, `tag:ESG`, `tag:Do Not Contact`.
- `Operational Servicing Role`: `Service Rep` is preserved in `source_tags` as `service_rep:Marcus Webb` (and `service_rep:A. Novak (departed)`) so administrative paperwork ownership is tracked, while strictly upholding Dana's rule that `Service Rep` is never mapped to `primary_advisor_id`.
- `Unused Columns`: Dropped with explicit provenance: `Cost_Basis` (tax-only per Dana) and `Website` (synthetic URLs).

### D. Currency & Financial Normalization
- Rule 5 mandates that all account figures be reported in `market_value_usd`.
- Converted using official **June 30, 2025 quarter-end central bank reference rates**:
  - **EUR**: `1.1720 USD per EUR` (official ECB reference rate on 2025-06-30 / Fed H.10: `1.1724`).
  - **CHF**: `1.2539 USD per CHF` (ECB reference rate on 2025-06-30: 1 EUR = 0.9347 CHF; Fed H.10: `1.2517`).
- Both accounts retain their original currency (`currency_original="EUR"`, `"CHF"`) and attach detailed `Provenance` records documenting the exchange rate and central bank source.

---

## 3. Business Rules Extracted from `sources/ops_slack_thread.md` & Lifecycle in `outputs/knowledge_base.json`

| Business Decision / Rule | Source / Authority | Encoded `KnowledgeRule` Key | Canonical Action & Provenance |
|---|---|---|---|
| `Status = Legacy` is the 2019 Harborline acquisition book; treat as active clients and keep lineage | Dana Ruiz (Slack Round 1) | `status_map:Legacy` (`scope="firm_specific"`) | `status = ACTIVE` + append `"lineage:harborline"` to `source_tags` (`provenance="slack_knowledge"`) |
| `Advisor` owns relationship; `Service Rep` is paperwork only — never fall back to `Service Rep` when `Advisor` is blank | Dana Ruiz (Slack Round 1) | `ignored_field:Service Rep` | Do not map `Service Rep` to `primary_advisor_id`; hold blank `Advisor` households (`Delgado`, `Whitfield`, `Petit`, `Vandermeer`) out of canonical output and flag to Dana |
| `A. Novak` (Anna Novak) is a contractor who left last year; surface records still pointing to her | Dana Ruiz (Slack Round 1) | `departed_staff:A. Novak` | Clear `A. Novak` from meeting `Attendee` (`Review — Delgado`) and flag `George Whitfield` / `Maria Delgado` for reassignment |
| AUM is always `Market_Value` as of quarter-end; ignore `Cost_Basis` | Dana Ruiz (Slack Round 1) | `ignored_field:Cost_Basis` | Drop `Cost_Basis`; compute `aum_usd` from `market_value_usd` (`provenance="slack_knowledge"`) |
| Convert EUR account (`Al-Rashid`, 1.875M EUR) to USD at quarter-end FX | Dana Ruiz (Slack Round 1) | `fx_rate:EUR` (`target="1.1720"`) | Convert to $2,197,500.00 USD at official ECB 2025-06-30 rate (1.1720; Fed H.10: 1.1724); record FX rule & rate in account provenance (`provenance="slack_knowledge"`) |
| Convert CHF account (`Bianchi`, 2.1M CHF at Pictet) to USD | FDE Assumption (Not in Slack) | `fx_rate:CHF` (`target="1.2539"`) | Convert to $2,633,190.00 USD at official ECB 2025-06-30 rate (1.2539; Fed H.10: 1.2517); record `provenance="assumption"` per Dana's general foreign-currency policy |
| `Dmitri Petrov` / `Petrov, Dmitri` is an import duplicate — collapse into one person | Dana Ruiz (Slack Round 1) | `duplicate_client:Petrov, Dmitri`, `meeting_client_alias:Petrov, Dmitri` | Drop duplicate client row, route meeting to `Petrov Household`, flag conflicting Fee/Risk values (`1.10%/Moderate` vs `1.00%/Aggressive`) to Dana |
| `Thompson` household (`Former` / `Churned`) left in 2023 and is winding down | Dana Ruiz (Slack Round 1) | `status_map:Former`, `status_map:Churned` | Map `Thompson Household` to `status = INACTIVE` |

### How Rules Auto-Apply on Next Sync & Get Corrected When Stale
- Every rule in [`outputs/knowledge_base.json`](outputs/knowledge_base.json) is keyed deterministically by `<rule_type>:<source_value>` with `version`, `active`, `scope` (`firm_specific` vs `global_reusable`), and `evidence`.
- On subsequent syncs, Stage 1 (`src/mapper.py`) queries `kb.get_rule(rule_type, source_value)` before creating an `UnresolvedCase`. On Sync #1 (cold start), records require LLM resolution; on Sync #2 (warm `outputs/knowledge_base.json`), learned rules auto-apply in Stage 1, cutting unresolved LLM cases down to the genuinely ambiguous records awaiting Dana's Round 2 answers.
- When a rule changes or is corrected by Dana in Round 2, `kb.upsert()` overwrites `<rule_type>:<source_value>`, increments `version`, and logs the transition in Logfire (`active=False` disables a stale rule immediately).
