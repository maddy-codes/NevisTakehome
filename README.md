# Nevis Forward Deployed Engineer — Agentic Onboarding Pipeline

An agentic data-mapping pipeline built with **PydanticAI** (`openai:gpt-5.6-luna`) and **Pydantic Logfire** that ingests Beaconcrest Advisors' messy Notion CRM export, custodian positions Excel workbook, advisor roster, and Round 1 onboarding Slack thread, and produces:

1. [`outputs/canonical_output.json`](outputs/canonical_output.json) — Validated mapped records across all 5 Nevis canonical entities (`advisors`, `households`, `clients`, `accounts`, `interactions`) carrying field-level provenance (`deterministic`, `slack_knowledge`, `llm`, `assumption`).
2. [`outputs/clarifications_round2.md`](outputs/clarifications_round2.md) — The customer-facing Round 2 executive memorandum for Dana Ruiz (Head of Operations) with scoped questions, triggers, exact evidence, candidate options, and proposed defaults.
3. [`outputs/blockers.md`](outputs/blockers.md) / `blockers.json` — The blocker ledger the resolver agent writes; the Round 2 memo is marked out of it.
4. [`outputs/knowledge_base.json`](outputs/knowledge_base.json) — The persistent knowledge layer capturing stakeholder rules from Round 1 Slack and entity resolutions so future syncs apply them automatically.
5. [`DESIGN.md`](DESIGN.md) — System architecture, data normalization details, trade-offs, and Slack business rules write-up.

---

## Repository Structure

```
Nevis/
├── README.md                          # Setup, verification, and run guide
├── DESIGN.md                          # Architecture, normalization, and Slack rules write-up
├── main.py                            # Pipeline orchestrator and entry point
├── pyproject.toml / requirements.txt  # Dependencies (PydanticAI, Logfire, Pandas, etc.)
│
├── outputs/                           # Committed deliverables produced by the run
│   ├── canonical_output.json          # Validated canonical records with provenance
│   ├── clarifications_round2.md       # Executive Round 2 memo for Dana Ruiz
│   └── knowledge_base.json            # Versioned knowledge rules
│
├── src/                               # Modular pipeline engine
│   ├── __init__.py
│   ├── models.py                      # Canonical Pydantic schemas & provenance models
│   ├── flag_matrix.py                 # Flag / don't-flag matrix given to the agent
│   ├── blockers.py                    # Blocker ledger writer, holdout coverage, memo fact-check
│   ├── knowledge.py                   # KnowledgeBase and KnowledgeRule store
│   ├── mapper.py                      # Stage 1 deterministic mapping & unmapped detector
│   ├── resolver.py                    # Stage 2 PydanticAI context builder & agent
│   └── assembler.py                   # Stage 3 canonical assembly & post-mapping validator
│
├── reference/                         # Caches, specifications, and reference documents
│   ├── llm_cache.json                 # Replay cache for offline zero-key evaluation
│   ├── canonical_model_erd.png
│   ├── Nevis - Canonical Data Model.pdf
│   └── Nevis - Forward Deployed Engineer Home Task.pdf
│
├── notebooks/                         # Interactive EDA notebook
│   └── exploration.ipynb              # EDA, categorical distributions, and note audits
│
└── sources/                           # Client raw input files
    ├── advisor_roster.csv
    ├── custodian_positions.xlsx
    ├── ops_slack_thread.md
    └── notion_export/
```

---

## Setup & Execution

### 1. Environment & Dependencies
Using `uv` (or the existing `.venv` virtual environment):

```bash
uv sync
```

### 2. Supply Your OpenAI API Key (Optional for Replay)
Set `OPENAI_API_KEY` in your environment or in `.env.local`:

```bash
export OPENAI_API_KEY="sk-..."
```

*(Optional: set `LOGFIRE_TOKEN` to stream OpenTelemetry traces to the Logfire cloud UI; console tracing works out of the box).*

### 3. Run the Pipeline End-to-End

```bash
.venv/bin/python main.py
```

- **Cold Start (first run)**: Delete `outputs/knowledge_base.json` (`rm -f outputs/knowledge_base.json && .venv/bin/python main.py`) to watch the PydanticAI agent extract all Round 1 Slack rules and Notion Markdown note links from scratch and populate `outputs/knowledge_base.json`.
- **Warm Sync (subsequent runs)**: Run `.venv/bin/python main.py` again with `outputs/knowledge_base.json` present to see Stage 1 (`src/mapper.py`) automatically apply learned rules before invoking the LLM only on remaining unresolved items.

### 4. Fallback Dry-Run Verification (Zero-Key Offline Mode)

To verify the pipeline end-to-end without calling live LLM APIs or overwriting the committed model results:

```bash
.venv/bin/python main.py --dry-run
```

This replays cached model decisions from `reference/llm_cache.json`, validates all 5 canonical entities and 7 canonical rules in memory, writes outputs to `outputs/dry_run_canonical_output.json`, and leaves the committed deliverables untouched.
