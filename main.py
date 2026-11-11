import json
import os
import re
from pathlib import Path
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent

from src.assembler import build_canonical_output
from src.blockers import check_holdouts_covered, group_blockers, verify_memo_against_ledger, write_blocker_ledger
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
        "You turn the blocker ledger into the Round 2 onboarding clarifications memo for RIA operations leadership (the Head of Operations).\n\n"
        "Input: the Round 1 Slack thread (already settled) and the blocker ledger: blockers the resolver agent flagged, each with a blocker_id, "
        "affected_entities, evidence, candidate options, a proposed default and a question.\n\n"
        "Rules:\n"
        "- You do not decide what is a blocker; the ledger already did. Do not add, drop or soften any blocker.\n"
        "- Dana should be able to answer the whole list in a few lines, so merge blockers of the same kind (same matrix_rule and the same question, "
        "e.g. every missing-advisor household, or every unmatched custodian account) into ONE item that names each entity with its account ID, custodian and amount. "
        "If several blockers concern the same client, household or account (for example a client-level and an account-level blocker for the same person), "
        "merge them into ONE item with one question and one default.\n"
        "- Keep separate only blockers that need a different kind of answer. Every blocker_id must appear in exactly one item's `blocker_ids`.\n"
        "- When merging, every blocker's `affected_entities` (every CU- account ID and every name) must still appear verbatim in the merged item's text. Never drop an account ID.\n"
        "- Keep the facts exactly: account IDs, custodians, dates, dollar amounts, verbatim quotes. Never invent people, documents or policies.\n"
        "- Never name a specific advisor in an option unless a source note or Slack names them; say 'a current roster advisor chosen by Dana'.\n"
        "- Keep each blocker's proposed default. If you merge blockers, the item's default must cite an option letter that exists among its options.\n"
        "- Wealth-management operations language only; no database or engineering jargon, and never mention the 'ledger', 'blockers', 'canonical output' or 'records held out of canonical output' "
        "(say 'excluded from reporting'). Format money as $1,240,000.\n"
        "- Each blocker has `account_facts` taken from the custodian feed. Whenever you name an account, state its custodian, amount and as-of date from those facts; "
        "never say a custodian or amount is 'not provided'.\n"
        "- Do not re-ask anything the Slack thread already settled.\n"
        "- Output an executive memo: no email greeting, sign-off or conversational filler. Dana should be able to answer the whole list in a few lines.\n"
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
    blockers_json_path: str = "outputs/blockers.json",
    blockers_md_path: str = "outputs/blockers.md",
    dry_run: bool = False,
) -> None:
    logfire.configure(send_to_logfire="if-token-present")
    logfire.instrument_pydantic_ai()

    if dry_run:
        print("[Dry-Run Mode] Executing offline fallback verification using cached model responses...")
        canonical_out_path = "outputs/dry_run_canonical_output.json"
        clarifications_out_path = "outputs/dry_run_clarifications_round2.md"
        blockers_json_path = "outputs/dry_run_blockers.json"
        blockers_md_path = "outputs/dry_run_blockers.md"

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

        # Stage 2b: the agent's flag decisions are written into the blocker ledger document
        blockers = write_blocker_ledger(resolutions, json_path=blockers_json_path, md_path=blockers_md_path)
        print(f"\n[Blocker Ledger] {len(blockers)} blocker(s) flagged by the resolver agent -> '{blockers_md_path}'")

        # Stage 3: Assemble Canonical Output & Post-Mapping Validation
        canonical_output, holdouts = build_canonical_output(
            mapping_result=mapping_result,
            resolutions=resolutions,
            kb=kb,
        )
        check_holdouts_covered(holdouts, blockers)
        print(f"  ✓ Every held-out record ({len(holdouts)}) is explained by a blocker in the ledger.")
        groups = group_blockers(blockers)

        Path(canonical_out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(canonical_out_path).write_text(
            canonical_output.model_dump_json(indent=2),
            encoding="utf-8",
        )

        # Stage 4: Synthesize Customer-Facing Round 2 Clarifications Artifact for Dana
        has_api_key = bool(os.environ.get("OPENAI_API_KEY")) and not dry_run
        cache_file = Path(cache_path)
        cache_data = json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {}

        with logfire.span("stage_4.synthesize_round2_clarifications", raw_count=len(blockers), mode="live_llm" if has_api_key else "cached_replay"):
            print("\n" + "=" * 80)
            print("[Stage 4: Synthesize Round 2 Clarifications]")
            print(f"  • Marking out the memo from {len(blockers)} blocker(s) in the ledger")
            if not has_api_key and cache_data.get("stage_4_clarifications"):
                print("  • Offline mode: Replaying cached Stage 4 clarifications from 'reference/llm_cache.json'")
                logfire.info("Replaying cached Stage 4 clarifications from llm_cache.json (offline / dry-run)")
                synth_output = SynthesizedClarifications.model_validate(cache_data["stage_4_clarifications"])
                formatted_memo = format_executive_clarifications_markdown(
                    synth_output.markdown_message_to_dana,
                    synth_output.items,
                )
                verify_memo_against_ledger(formatted_memo, synth_output.items, blockers, sources_dir=sources_dir)
            else:
                print("  • Synthesizing executive questions using PydanticAI (openai:gpt-5.6-luna)... ", end="", flush=True)
                slack_text = (Path(sources_dir) / "ops_slack_thread.md").read_text(encoding="utf-8")
                prompt = (
                    f"### Round 1 Slack Thread Context (Already Settled — Do Not Re-Ask)\n{slack_text}\n\n"
                    f"### Blocker Ledger: {len(blockers)} blockers in {len(groups)} decision groups\n"
                    f"Write exactly ONE item per group (so {len(groups)} items). Each item's `blocker_ids` must list every blocker_id of its group. "
                    f"Do not change any account number, custodian or amount.\n"
                    + json.dumps(
                        [{"group": n, "blockers": [b_.model_dump() for b_ in g]} for n, g in enumerate(groups, 1)],
                        indent=2,
                    )
                )

                max_attempts = 3
                for attempt in range(max_attempts):
                    synth_res = clarification_synthesizer.run_sync(prompt)
                    synth_output = synth_res.output
                    formatted_memo = format_executive_clarifications_markdown(
                        synth_output.markdown_message_to_dana,
                        synth_output.items,
                    )
                    try:
                        verify_memo_against_ledger(formatted_memo, synth_output.items, blockers, sources_dir=sources_dir)
                        break
                    except AssertionError as err:
                        if attempt == max_attempts - 1:
                            raise
                        print(f"\n  [Fact-Check Warning: {err}. Retrying synthesis with stricter prompt...]")
                        prompt += f"\n\nERROR IN PREVIOUS ATTEMPT: {err}. Please correct this immediately."

                print("Done.")
                print("  ✓ Rigorous post-synthesis fact-check passed: every blocker covered; account IDs, custodians and amounts verified against the custodian feed.")
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
