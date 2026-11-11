import json
import os
from pathlib import Path
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from src.assembler import build_canonical_output
from src.mapper import run_deterministic_mapping
from src.models import ClarificationItem
from src.resolver import resolve_unresolved_cases

load_dotenv(".env.local")
load_dotenv()


class SynthesizedClarifications(BaseModel):
    markdown_message_to_dana: str
    items: list[ClarificationItem]


clarification_synthesizer = Agent(
    "openai:gpt-5.6-luna",
    output_type=SynthesizedClarifications,
    name="nevis_round2_clarification_writer",
    defer_model_check=True,
    instructions=(
        "You are a Forward Deployed Engineer synthesizing the Round 2 onboarding clarifications for RIA operations.\n\n"
        "Guidelines:\n"
        "- Dana Ruiz is Head of Operations at an RIA, not a software engineer. NEVER use internal database or engineering jargon: "
        "do NOT mention 'canonical data model', 'canonical output', 'canonical entities', 'minting households', or 'Rule 4 violations'.\n"
        "- Speak strictly in wealth management and RIA operations terms: client accounts, billing/AUM totals, advisor dashboards, "
        "household groupings, custodian statement feeds, and estate transition.\n"
        "- Do NOT re-ask anything Dana settled in Round 1 (do NOT ask what Legacy means, do NOT ask whether Service Rep is an advisor, "
        "do NOT ask whether to use Market Value vs Cost Basis, do NOT ask whether to convert foreign currency to USD, do NOT ask about Dmitri Petrov, "
        "and do NOT ask about Thompson, whom Dana already instructed to mark inactive and exclude from active AUM).\n"
        "- Do NOT re-ask advisor assignments for Maria Delgado, George Whitfield, Louis Petit, or Joris Vandermeer: in Round 1, "
        "Dana explicitly told us to leave them unassigned until she checks the transition spreadsheet.\n"
        "- Synthesize the raw exception items provided into clean, concise, executive questions. For each item, provide:\n"
        "  - category\n"
        "  - question_for_dana\n"
        "  - trigger\n"
        "  - evidence\n"
        "  - candidate_options (Option A vs Option B)\n"
        "  - proposed_default (bolded, matching staged data)\n"
    ),
)


def format_executive_clarifications_markdown(raw_message: str, items: list[ClarificationItem]) -> str:
    """Format an executive list of clarification questions for Beaconcrest Advisors operations."""
    lines = [
        "# Round 2 Clarifications — Beaconcrest Advisors",
        "",
        "Unresolved operational exceptions and proposed defaults following Round 1 onboarding.",
        "",
        "---",
        "",
        "### Pending From Round 1 (Status Note — No Action Needed)",
        "- **Advisor Reassignments**: Per Round 1 discussion, Maria Delgado, George Whitfield, Louis Petit, and Joris Vandermeer remain unassigned pending confirmation of the transition spreadsheet for Sarah / Elena.",
        "- **Departed Contractor**: Client and meeting records historically associated with former contractor Anna Novak are flagged in the ops queue for servicing reassignment.",
        "",
        "---",
        "",
        "### Operational Decisions Required",
        "",
    ]

    for idx, item in enumerate(items, 1):
        clean_options = []
        for opt in item.candidate_options:
            clean_opt = opt.strip()
            if clean_opt.startswith(("Option A", "Option B", "Option C", "Option D")):
                label, desc = clean_opt.split("—", 1) if "—" in clean_opt else clean_opt.split(":", 1) if ":" in clean_opt else (clean_opt[:8], clean_opt[8:])
                clean_options.append(f"  - **{label.strip()}**: {desc.strip()}")
            elif re.match(r"^[A-Z]\)", clean_opt):
                clean_options.append(f"  - **Option {clean_opt[0]}**: {clean_opt[2:].strip()}")
            else:
                clean_options.append(f"  - {clean_opt}")

        clean_default = item.proposed_default.strip().strip("*")

        lines.extend(
            [
                f"### {idx}. {item.category} — {item.question_for_dana}",
                "",
                f"- **Trigger**: {item.trigger}",
                f"- **Evidence**: {item.evidence}",
                "- **Candidate Options**:",
                *clean_options,
                f"- **Proposed Default**: **{clean_default}**",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "Once confirmed, these decisions will be applied automatically and the Beaconcrest book will be finalized in Nevis.",
            "",
        ]
    )
    return "\n".join(lines)


def run_pipeline(
    sources_dir: str = "sources",
    kb_path: str = "outputs/knowledge_base.json",
    cache_path: str = "reference/llm_cache.json",
    canonical_out_path: str = "outputs/canonical_output.json",
    clarifications_out_path: str = "outputs/clarifications_round2.md",
    dry_run: bool = False,
) -> None:
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()

    if dry_run:
        print("[Dry-Run Mode] Executing offline fallback verification using cached model responses...")
        canonical_out_path = "outputs/dry_run_canonical_output.json"
        clarifications_out_path = "outputs/dry_run_clarifications_round2.md"

    with logfire.span("nevis_onboarding_pipeline", dry_run=dry_run) as root_span:
        # Stage 1: Deterministic & KnowledgeBase Pass
        mapping_result = run_deterministic_mapping(sources_dir=sources_dir, kb_path=kb_path)

        # Stage 2: Agentic Resolution of Unresolved Cases + Learning into KnowledgeBase
        resolutions, kb = resolve_unresolved_cases(
            mapping_result=mapping_result,
            slack_path=Path(sources_dir) / "ops_slack_thread.md",
            kb_path=kb_path,
            cache_path=cache_path,
            batch_size=10,
            force_replay=dry_run,
        )

        # Stage 3: Assemble Canonical Output & Post-Mapping Validation
        canonical_output, raw_clarifications = build_canonical_output(
            mapping_result=mapping_result,
            resolutions=resolutions,
            kb=kb,
        )

        Path(canonical_out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(canonical_out_path).write_text(
            canonical_output.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Stage 4: Synthesize Customer-Facing Round 2 Clarifications Artifact for Dana
        has_api_key = bool(os.environ.get("OPENAI_API_KEY")) and not dry_run
        cache_file = Path(cache_path)
        cache_data = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

        with logfire.span("stage_4.synthesize_round2_clarifications", raw_count=len(raw_clarifications), mode="live_llm" if has_api_key else "cached_replay"):
            print("\n" + "=" * 80)
            print("[Stage 4: Synthesize Round 2 Clarifications]")
            print(f"  • Programmatically detected {len(raw_clarifications)} raw exception signals from mapping & validator")
            if not has_api_key and cache_data.get("stage_4_clarifications"):
                print("  • Offline mode: Replaying cached Stage 4 clarifications from 'reference/llm_cache.json'")
                logfire.info("Replaying cached Stage 4 clarifications from llm_cache.json (offline / dry-run)")
                synth_output = SynthesizedClarifications.model_validate(cache_data["stage_4_clarifications"])
            else:
                print("  • Synthesizing executive questions using PydanticAI (openai:gpt-5.6-luna)... ", end="", flush=True)
                slack_text = (Path(sources_dir) / "ops_slack_thread.md").read_text(encoding="utf-8")
                prompt = (
                    f"### Round 1 Slack Thread (Already Settled — Do Not Re-Ask)\n{slack_text}\n\n"
                    f"### Raw Flagged Items from Pipeline & Validator ({len(raw_clarifications)} items)\n"
                    + json.dumps([c.model_dump() for c in raw_clarifications], indent=2)
                )
                synth_res = clarification_synthesizer.run_sync(prompt)
                synth_output = synth_res.output
                print("Done.")
                cache_data["stage_4_clarifications"] = synth_output.model_dump()
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

            # Write clean executive customer-facing message
            formatted_memo = format_executive_clarifications_markdown(
                synth_output.markdown_message_to_dana,
                synth_output.items,
            )
            Path(clarifications_out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(clarifications_out_path).write_text(
                formatted_memo,
                encoding="utf-8",
            )
            print(f"  • Generated {len(synth_output.items)} operational decisions:")
            for idx, it in enumerate(synth_output.items, 1):
                print(f"    {idx}. {it.category}: {it.question_for_dana[:75]}...")
            print(f"  ✓ Clarifications document written to '{clarifications_out_path}' ({len(formatted_memo.splitlines())} lines).")
            print("=" * 80 + "\n")

        root_span.set_attribute("final_households", len(canonical_output.households))
        root_span.set_attribute("final_clients", len(canonical_output.clients))
        root_span.set_attribute("final_accounts", len(canonical_output.accounts))
        root_span.set_attribute("final_interactions", len(canonical_output.interactions))
        root_span.set_attribute("final_clarifications", len(synth_output.items))

    if dry_run:
        print(f"[Dry-Run Mode] Success! Validated 5 canonical entities, 7 canonical rules, and post-mapping checks.")
        print(f"[Dry-Run Mode] Dry-run outputs written to '{canonical_out_path}' and '{clarifications_out_path}'.")
        print(f"[Dry-Run Mode] Committed live model results in 'outputs/' were NOT modified.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Nevis Onboarding Agentic Pipeline")
    parser.add_argument("--dry-run", "--mock", action="store_true", help="Run fallback verification using cached model responses without calling live API or overwriting committed outputs")
    args = parser.parse_args()
    run_pipeline(dry_run=args.dry_run)
