# Nevis Forward Deployed Engineer — Agentic Onboarding Pipeline

An agentic data-mapping pipeline built with **PydanticAI** (`openai:gpt-5.6-luna`) and **Pydantic Logfire** that ingests Beaconcrest Advisors' messy Notion CRM export, custodian positions Excel workbook, advisor roster, and Round 1 onboarding Slack thread, and produces:

1. [`canonical_output.json`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/canonical_output.json) — High-confidence mapped records across all 5 Nevis canonical entities (`advisors`, `households`, `clients`, `accounts`, `interactions`) with field-level provenance (`deterministic`, `slack_knowledge`, `llm`).
2. [`clarifications_round2.md`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/clarifications_round2.md) — The customer-facing Round 2 message to Dana Ruiz (Head of Operations) with scoped questions, triggers, exact evidence, candidate options, and proposed defaults.
3. [`knowledge_base.json`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/knowledge_base.json) — The persistent knowledge layer capturing stakeholder rules from Round 1 Slack and entity resolutions so future syncs apply them automatically.
4. [`DESIGN.md`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/DESIGN.md) — One-page architecture, trade-offs, and Slack business rules write-up.

---

## Setup & One-Command Run

### 1. Environment & Dependencies
Using `uv` (or the existing `.venv` virtual environment):

```bash
uv sync
```

### 2. Supply Your OpenAI API Key
Set `OPENAI_API_KEY` in your environment or in `.env.local`:

```bash
export OPENAI_API_KEY="sk-..."
```

*(Optional: set `LOGFIRE_TOKEN` to stream OpenTelemetry traces to the Logfire cloud UI; console tracing works out of the box).*

### 3. Run the Pipeline End-to-End

```bash
.venv/bin/python main.py
```

- **Cold Start (first run)**: Delete `knowledge_base.json` (`rm -f knowledge_base.json && .venv/bin/python main.py`) to watch the PydanticAI agent extract all Round 1 Slack rules and Notion Markdown note links from scratch and populate `knowledge_base.json`.
- **Warm Sync (subsequent runs)**: Run `.venv/bin/python main.py` again with `knowledge_base.json` present to see Stage 1 (`mapper.py`) automatically apply 26 learned rules before invoking the LLM only on the remaining unresolved items.

---

## Repository Structure

- [`models.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/models.py) — Canonical Pydantic schemas (`Advisor`, `Household`, `Client`, `Account`, `Interaction`, `Provenance`, `ClarificationItem`).
- [`knowledge.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/knowledge.py) — Persistent, versioned `KnowledgeBase` and `KnowledgeRule` store (`knowledge_base.json`).
- [`mapper.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/mapper.py) — Stage 1 deterministic parser (including Notion Markdown page body extraction) + KnowledgeBase lookup + `UnresolvedCase` detector.
- [`resolver.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/resolver.py) — Stage 2 cross-source context builder and PydanticAI `nevis_ambiguity_resolver` agent instrumented with Logfire.
- [`assembler.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/assembler.py) — Stage 3 canonical entity assembler and post-mapping validator enforcing all 7 Nevis Canonical Rules and catching cross-record spouse conflicts.
- [`main.py`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/main.py) — End-to-end orchestrator and Stage 4 Round 2 clarification synthesizer.
- [`exploration.ipynb`](file:///Users/jatinarora/Desktop/PersonalApplications/Nevis/exploration.ipynb) — Exploratory data analysis notebook covering missingness, dirty categorical distributions, Notion Markdown note extraction, and cross-table relationship audits.

