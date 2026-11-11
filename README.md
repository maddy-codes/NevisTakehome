# Nevis Onboarding Pipeline

An agentic pipeline that maps Beaconcrest Advisors' Notion CRM export, custodian positions, advisor roster and Round 1 Slack thread into the Nevis canonical model. An LLM agent (PydanticAI, `openai:gpt-5.6-luna`, traced with Logfire) decides what it can resolve confidently and what is a blocker. Blockers are written to a ledger, and the Round 2 questions for Dana are marked out of that ledger.

## What it produces

| File | Contents |
|---|---|
| [`outputs/canonical_output.json`](outputs/canonical_output.json) | Records the system mapped confidently: advisors, households, clients, accounts, interactions, each value carrying provenance (`deterministic`, `slack_knowledge`, `llm`, `assumption`). |
| [`outputs/clarifications_round2.md`](outputs/clarifications_round2.md) | The Round 2 message to Dana: one scoped question per decision with trigger, evidence, candidate options and a proposed default. Nothing Slack already settled is re-asked. |
| [`outputs/blockers.md`](outputs/blockers.md) / [`blockers.json`](outputs/blockers.json) | The ledger the agent writes: every blocker it flagged (with the flag-matrix rule that justified it) and a list of cases it decided without flagging. |
| [`outputs/field_dispositions.md`](outputs/field_dispositions.md) | Every source column and where it goes (mapped, normalized, preserved as a tag, agent-read, or dropped with a reason). |
| [`outputs/knowledge_base.json`](outputs/knowledge_base.json) | Reusable business rules (from Slack and from agent resolutions) that apply automatically on the next sync. |
| [`DESIGN.md`](DESIGN.md) | Design note, trade-offs and the Slack rules write-up. |

## Setup

Requires Python 3.11 and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

Add an OpenAI key to `.env.local` (or export it):

```bash
OPENAI_API_KEY=sk-...
```

Optional: set `LOGFIRE_TOKEN` to send traces to Logfire. Console tracing works without it.

## Run

```bash
uv run python main.py
```

This runs all four stages against the files in `sources/`, calls the live model, and overwrites the files in `outputs/` and the replay cache in `reference/llm_cache.json`. It takes a couple of minutes. The model is not deterministic, so a re-run can flag slightly differently. The committed outputs are one live run.

### Without an API key

```bash
uv run python main.py --dry-run
```

Replays the cached model decisions from `reference/llm_cache.json`, re-runs the deterministic stages and all validations, and writes `outputs/dry_run_*` files. It leaves the committed deliverables untouched.

## How it works

1. **Deterministic pass** (`src/mapper.py`): normalizes dates, names and enums, applies knowledge-base rules, and lists candidate cases for the agent.
2. **Agentic resolution** (`src/resolver.py`): the agent chooses auto-apply, collapse a duplicate, or flag, using the flag / don't-flag matrix in `src/flag_matrix.py`. A flag must carry a typed blocker.
3. **Blocker ledger** (`src/blockers.py`): flagged blockers are written to `outputs/blockers.*`.
4. **Assembly and validation** (`src/assembler.py`): builds the canonical records, applies each blocker's default action, converts currency, and asserts the 7 canonical rules. Any record held out without a blocker fails the run.
5. **Round 2 memo** (`main.py`): grouped blockers become one decision each, and a fact-check verifies account IDs, custodians, amounts and option and default consistency against the source files.

See [`DESIGN.md`](DESIGN.md) for the rules, trade-offs and how Slack answers are encoded.

## Repository layout

```
main.py                 pipeline entry point
src/
  models.py             canonical schemas, provenance, Blocker, Holdout
  flag_matrix.py        what to flag and what not to flag
  field_map.py          a disposition for every source column (fails on an unknown one)
  mapper.py             stage 1
  resolver.py           stage 2 agent
  blockers.py           ledger writer, holdout coverage, memo fact-check
  assembler.py          stage 3
  knowledge.py          KnowledgeBase / KnowledgeRule store
sources/                client inputs (Notion export, custodian xlsx, roster, Slack thread)
outputs/                committed deliverables
reference/              replay cache, task brief, canonical model
notebooks/              exploratory analysis
```
