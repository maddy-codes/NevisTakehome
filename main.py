import json
from pathlib import Path
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from assembler import build_canonical_output
from mapper import run_deterministic_mapping
from models import ClarificationItem
from resolver import resolve_unresolved_cases

load_dotenv(".env.local")
load_dotenv()


class SynthesizedClarifications(BaseModel):
    markdown_message_to_dana: str
    items: list[ClarificationItem]


def format_clarifications_markdown(synth: SynthesizedClarifications) -> str:
    lines = [synth.markdown_message_to_dana.strip(), "", "---", "", "## Detailed Clarification Specifications"]
    for idx, item in enumerate(synth.items, 1):
        lines.extend(
            [
                f"### {idx}. [{item.category}] {item.question_for_dana}",
                f"- **ID**: `{item.id}`",
                f"- **Trigger**: {item.trigger}",
                f"- **Evidence**: {item.evidence}",
                f"- **Candidate Options**:",
                *[f"  - {opt}" for opt in item.candidate_options],
                f"- **Proposed Default**: {item.proposed_default}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


clarification_synthesizer = Agent(
    "openai:gpt-5.6-luna",
    output_type=SynthesizedClarifications,
    name="nevis_round2_clarification_writer",
    instructions=(
        "You are Alex, Forward Deployed Engineer at Nevis, writing the Round 2 onboarding message to "
        "Dana Ruiz (Head of Operations at Beaconcrest Advisors).\n\n"
        "Strict requirements from the brief:\n"
        "1. You have already read Round 1 (`sources/ops_slack_thread.md`). NEVER re-ask anything Dana already settled in Round 1 "
        "(do NOT ask what Legacy means, do NOT ask whether Service Rep is the advisor, do NOT ask whether to use Market Value vs Cost Basis, "
        "do NOT ask whether to convert EUR to USD for Al-Rashid, do NOT ask whether Dmitri Petrov is a duplicate, and do NOT ask whether Thompson is inactive).\n"
        "2. Group related raw clarification items (e.g., all 4 unassigned-advisor households together; all spouse/duplicate Risk Profile & Fee Schedule conflicts + Tier 1/Tier 2/See LOE definitions together; "
        "both orphan custodian accounts together; stale active account dates together) into a tight, numbered shortlist of 6–7 clean questions so Dana can reply in a few lines.\n"
        "3. Every single item MUST clearly state:\n"
        "   - **Trigger**: What triggered it\n"
        "   - **Evidence**: Exact account numbers, names, balances, dates, or CRM notes\n"
        "   - **Candidate Options**: Concrete options (A / B)\n"
        "   - **Proposed Default**: Our recommended default if she agrees\n"
    ),
)


def run_pipeline(
    sources_dir: str = "sources",
    kb_path: str = "knowledge_base.json",
    canonical_out_path: str = "canonical_output.json",
    clarifications_out_path: str = "clarifications_round2.md",
) -> None:
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()

    with logfire.span("nevis_onboarding_pipeline") as root_span:
        # Stage 1: Deterministic & KnowledgeBase Pass
        mapping_result = run_deterministic_mapping(sources_dir=sources_dir, kb_path=kb_path)

        # Stage 2: Agentic Resolution of Unresolved Cases + Learning into KnowledgeBase
        resolutions, kb = resolve_unresolved_cases(
            mapping_result=mapping_result,
            slack_path=Path(sources_dir) / "ops_slack_thread.md",
            kb_path=kb_path,
            batch_size=10,
        )

        # Stage 3: Assemble Canonical Output & Post-Mapping Validation
        canonical_output, raw_clarifications = build_canonical_output(
            mapping_result=mapping_result,
            resolutions=resolutions,
            kb=kb,
        )

        Path(canonical_out_path).write_text(
            canonical_output.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Stage 4: Synthesize Customer-Facing Round 2 Clarifications Artifact for Dana
        with logfire.span("stage_4.synthesize_round2_clarifications", raw_count=len(raw_clarifications)):
            slack_text = (Path(sources_dir) / "ops_slack_thread.md").read_text(encoding="utf-8")
            prompt = (
                f"### Round 1 Slack Thread (Already Settled — Do Not Re-Ask)\n{slack_text}\n\n"
                f"### Raw Flagged Items from Pipeline & Validator ({len(raw_clarifications)} items)\n"
                + json.dumps([c.model_dump() for c in raw_clarifications], indent=2)
            )
            synth_res = clarification_synthesizer.run_sync(prompt)
            Path(clarifications_out_path).write_text(
                format_clarifications_markdown(synth_res.output),
                encoding="utf-8",
            )

        root_span.set_attribute("final_households", len(canonical_output.households))
        root_span.set_attribute("final_clients", len(canonical_output.clients))
        root_span.set_attribute("final_accounts", len(canonical_output.accounts))
        root_span.set_attribute("final_interactions", len(canonical_output.interactions))
        root_span.set_attribute("final_clarifications", len(synth_res.output.items))


if __name__ == "__main__":
    run_pipeline()
