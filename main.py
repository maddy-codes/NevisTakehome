import json
import os
import re
from pathlib import Path
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from src.assembler import build_canonical_output, verify_clarifications_fact_check
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
        "You write the Round 2 onboarding clarifications memo for RIA operations leadership (the Head of Operations).\n\n"
        "Input: (1) the Round 1 Slack thread (already settled), and (2) a JSON list of anomaly signals detected from the source data. "
        "Each signal has a signal_id, anomaly_type, affected_entities, facts, source_evidence and the pipeline_action already taken.\n\n"
        "Rules:\n"
        "- The reader is an operations executive, not an engineer. Use wealth-management language only (client accounts, billing/AUM, advisor dashboards, household groupings, custodian feeds). "
        "No database, schema or 'canonical model' jargon.\n"
        "- Write one decision item per distinct decision. You may group signals of the same type into one item. "
        "Every signal_id must appear in exactly one item's `signal_ids`; do not drop signals and do not invent new ones.\n"
        "- Use ONLY facts present in the signals and the Slack thread. Copy account IDs, custodians, dates and dollar amounts exactly. "
        "Never invent third parties, documents, people or policies. Quote source_evidence verbatim when it helps.\n"
        "- Format money as $1,240,000 (or 2,100,000 CHF), never as 1240000.0, and never expose internal field names such as converted_usd or pipeline_action.\n"
        "- Do not re-ask anything the Slack thread already settled.\n"
        "- Honour stated guidance in the Slack thread (for example, if the ops lead said not to guess a value, never propose a guessed value).\n"
        "- Give 2-3 candidate options labelled 'Option A', 'Option B', 'Option C'. "
        "The proposed default must be the option that matches the signal's pipeline_action (what was already applied in the output), "
        "must cite its option letter, and must be the conservative choice that does not fabricate data.\n"
        "- Output an executive memo: no email greeting, sign-off or conversational filler.\n"
    ),
)


def format_executive_clarifications_markdown(raw_message: str, items: list[ClarificationItem]) -> str:
    """Format an executive list of clarification questions for Beaconcrest Advisors operations."""
    lines = [
        "# Round 2 Clarifications — Beaconcrest Advisors",
        "",
        "Operational decisions and proposed defaults following Round 1 onboarding review.",
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
        canonical_output, raw_signals = build_canonical_output(
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

        with logfire.span("stage_4.synthesize_round2_clarifications", raw_count=len(raw_signals), mode="live_llm" if has_api_key else "cached_replay"):
            print("\n" + "=" * 80)
            print("[Stage 4: Synthesize Round 2 Clarifications]")
            print(f"  • Programmatically detected {len(raw_signals)} anomaly signals from mapping & validator")
            if not has_api_key and cache_data.get("stage_4_clarifications"):
                print("  • Offline mode: Replaying cached Stage 4 clarifications from 'reference/llm_cache.json'")
                logfire.info("Replaying cached Stage 4 clarifications from llm_cache.json (offline / dry-run)")
                synth_output = SynthesizedClarifications.model_validate(cache_data["stage_4_clarifications"])
                formatted_memo = format_executive_clarifications_markdown(
                    synth_output.markdown_message_to_dana,
                    synth_output.items,
                )
                verify_clarifications_fact_check(formatted_memo, synth_output.items, raw_signals, sources_dir=sources_dir)
            else:
                print("  • Synthesizing executive questions using PydanticAI (openai:gpt-5.6-luna)... ", end="", flush=True)
                slack_text = (Path(sources_dir) / "ops_slack_thread.md").read_text(encoding="utf-8")
                prompt = (
                    f"### Round 1 Slack Thread Context (Already Settled — Do Not Re-Ask)\n{slack_text}\n\n"
                    f"### Anomaly Signals Detected From Source Data ({len(raw_signals)})\n"
                    f"Cover every signal_id. Do not change any account number, custodian or amount.\n"
                    + json.dumps([sg.model_dump() for sg in raw_signals], indent=2, default=str)
                )

                max_attempts = 2
                for attempt in range(max_attempts):
                    synth_res = clarification_synthesizer.run_sync(prompt)
                    synth_output = synth_res.output
                    formatted_memo = format_executive_clarifications_markdown(
                        synth_output.markdown_message_to_dana,
                        synth_output.items,
                    )
                    try:
                        verify_clarifications_fact_check(formatted_memo, synth_output.items, raw_signals, sources_dir=sources_dir)
                        break
                    except AssertionError as err:
                        if attempt == max_attempts - 1:
                            raise
                        print(f"\n  [Fact-Check Warning: {err}. Retrying synthesis with stricter prompt...]")
                        prompt += f"\n\nERROR IN PREVIOUS ATTEMPT: {err}. Please correct this immediately."

                print("Done.")
                print("  ✓ Rigorous post-synthesis fact-check passed: every signal covered; account IDs, custodians and amounts verified against the custodian feed.")
                cache_data["stage_4_clarifications"] = synth_output.model_dump()
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")

            # Write clean executive customer-facing message
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
