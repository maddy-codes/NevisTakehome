import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext

from src.flag_matrix import FLAG_MATRIX
from src.knowledge import KnowledgeBase, KnowledgeRule
from src.mapper import DeterministicMappingResult, UnresolvedCase
from src.models import (
    AccountType,
    Blocker,
    ClientRole,
    HouseholdStatus,
    InteractionType,
    ProvenanceSource,
)

load_dotenv(".env.local")
load_dotenv()


class CaseResolution(BaseModel):
    case_id: str
    action: Literal["auto_apply", "drop_duplicate", "flag_for_clarification"]
    confidence: float = Field(ge=0.0, le=1.0)
    provenance_source: ProvenanceSource
    evidence: str
    resolved_household_name: str | None = None
    resolved_advisor_id: str | None = None
    resolved_status: HouseholdStatus | None = None
    resolved_client_role: ClientRole | None = None
    resolved_account_type: AccountType | None = None
    resolved_interaction_type: InteractionType | None = None
    resolved_market_value_usd: float | None = None
    added_source_tags: list[str] = Field(default_factory=list)
    learned_rules: list[KnowledgeRule] = Field(default_factory=list)
    blocker: Blocker | None = None

    @model_validator(mode="after")
    def _flag_decision_is_consistent(self) -> "CaseResolution":
        if self.action == "flag_for_clarification" and self.blocker is None:
            raise ValueError("action=flag_for_clarification requires a `blocker` citing a flag-matrix rule (F1-F7).")
        if self.action != "flag_for_clarification" and self.blocker is not None:
            raise ValueError("Only flag_for_clarification may carry a `blocker`; do not flag DO-NOT-FLAG situations (D1-D10).")
        if self.blocker is not None and not self.blocker.affected_entities:
            raise ValueError("blocker.affected_entities must list the account ids / names the question is about.")
        return self


class BatchResolutionOutput(BaseModel):
    resolutions: list[CaseResolution]


@dataclass
class ResolutionDeps:
    mapping_result: DeterministicMappingResult
    slack_thread: str
    knowledge_base: KnowledgeBase


def build_case_context(case: UnresolvedCase, deps: ResolutionDeps) -> dict[str, Any]:
    """Assemble cross-source context (matching CRM clients/notes, custodian accounts, and meetings)."""
    raw = case.raw_record
    name_or_holder = (
        raw.get("Name") or raw.get("Account_Holder") or raw.get("Client") or raw.get("Household") or ""
    )
    tokens = [
        t.strip(".,()—-")
        for t in name_or_holder.replace("&", " ").split()
        if len(t.strip(".,()—-")) >= 3
        and t.lower()
        not in {"llc", "trust", "revocable", "joint", "review", "call", "intro", "check-in", "annual", "qbr"}
    ]

    def _matches(record: dict[str, Any]) -> bool:
        blob = " ".join(str(v) for v in record.values() if v is not None).lower()
        return any(tok.lower() in blob for tok in tokens)

    matching_clients = [
        {k: v for k, v in c.items() if not k.startswith("_")}
        for c in deps.mapping_result.all_clients_raw
        if _matches(c)
    ]
    matching_accounts = [
        {k: v for k, v in a.items() if not k.startswith("_")}
        for a in deps.mapping_result.all_accounts_raw
        if _matches(a)
    ]
    matching_meetings = [
        {k: v for k, v in m.items() if not k.startswith("_")}
        for m in deps.mapping_result.all_interactions_raw
        if _matches(m)
    ]

    return {
        "case_id": case.case_id,
        "entity_type": case.entity_type,
        "reasons": case.reasons,
        "raw_record": {k: v for k, v in raw.items() if not k.startswith("_")},
        "related_context": {
            "matching_crm_clients_and_notes": matching_clients,
            "matching_custodian_accounts": matching_accounts,
            "matching_meetings": matching_meetings,
        },
    }


resolution_agent = Agent(
    "openai:gpt-5.6-luna",
    deps_type=ResolutionDeps,
    output_type=BatchResolutionOutput,
    name="nevis_ambiguity_resolver",
    defer_model_check=True,
    retries=4,  # nested Blocker schema: let the model repair schema misses instead of failing the run
    instructions=(
        "You are a Forward Deployed Engineer agent mapping a wealth management firm's source data "
        "(Notion CRM exports + custodian positions spreadsheet + advisor roster) into the Nevis Canonical Data Model.\n\n"
        "For each case you decide: auto-apply with provenance, collapse a confirmed duplicate, or flag it as a blocker for the client's operations lead. "
        "Auto-apply as much as you confidently can; flag only what a person must decide. Silent guessing and over-flagging are both wrong.\n\n"
        "### Nevis Canonical Rules\n"
        "1. One primary advisor per household (required, non-null). Never guess an advisor from a secondary/service role if the stakeholder forbade it.\n"
        "2. AUM is market value in USD; household AUM is the sum of its accounts.\n"
        "3. Unknown != zero. A household with no known accounts has AUM null.\n"
        "4. Every account rolls up to exactly one household. No orphan accounts.\n"
        "5. Non-USD balances are converted to USD (the assembler applies the quarter-end rate; do not compute it and do not flag it).\n"
        "6. Fields with no first-class home: preserve business-meaningful attributes as `added_source_tags`, drop irrelevant ones, flag only genuine contradictions.\n"
        "7. Every interaction rolls up to an existing household. Never mint a household from an interaction.\n\n"
        + FLAG_MATRIX
        + "\n### How to write a blocker\n"
        "- `matrix_rule` is the F-rule that justifies the flag. `affected_entities` lists the exact account ids, client names and meeting names involved.\n"
        "- Use only facts in the case context and the Slack thread; quote notes verbatim; never invent people, documents or policies.\n"
        "- Give 2-3 options labelled 'Option A', 'Option B', 'Option C'. The `proposed_default` must cite one option letter and be the conservative choice "
        "that does not fabricate data. Set `default_action` to its mechanical effect, which the assembler applies verbatim: "
        "`hold_out` (record stays out of canonical output), `retain_and_tag` (kept with its original values and date, tagged pending), "
        "or `set_inactive` (household INACTIVE, tagged pending). `default_action` must agree with `proposed_default`.\n"
        "- Never name a specific advisor, household or value in an option unless a source note or Slack message names it. "
        "Write 'a current roster advisor chosen by Dana' instead of picking a person: choosing one is guessing.\n"
        "- Write in wealth-management operations language: no database or engineering jargon. Format money as $1,240,000.\n"
        "- Do not re-ask anything the Slack thread already settled.\n\n"
        "### Strict Provenance Attribution (`provenance_source`)\n"
        "- `slack_knowledge` ONLY when the Slack thread explicitly settled that exact rule or entity.\n"
        "- `llm` when you resolved an entity link, nickname, abbreviated advisor name, spouse link or joint/trust/abbreviated holder from the CRM records and notes.\n"
        "- `assumption` when applying a default pending confirmation.\n\n"
        "### Learned Rules (`learned_rules`)\n"
        "Emit a `KnowledgeRule` for reusable mappings (`status_map`, `advisor_alias`, `departed_staff`, `duplicate_client`, `household_link`, "
        "`account_holder_to_household`, `meeting_client_alias`, `fx_rate`, `ignored_field`) with accurate `provenance_source`. "
        "Never emit a reusable rule for a record you flagged under F2, F4, F6 or F7: an undecided link must not be learned as settled."
    ),
)


@resolution_agent.system_prompt
def add_dynamic_context(ctx: RunContext[ResolutionDeps]) -> str:
    advisors_str = "\n".join(
        f"- {a.advisor_id}: {a.full_name} ({a.role})" for a in ctx.deps.mapping_result.advisors
    )
    existing_rules_str = (
        json.dumps([r.model_dump() for r in ctx.deps.knowledge_base.rules.values()], indent=2)
        if ctx.deps.knowledge_base.rules
        else "None yet"
    )
    return (
        f"### Advisor Roster\n{advisors_str}\n\n"
        f"### Round 1 Onboarding Slack Thread (sources/ops_slack_thread.md)\n{ctx.deps.slack_thread}\n\n"
        f"### Existing KnowledgeBase Rules\n{existing_rules_str}"
    )


def resolve_unresolved_cases(
    mapping_result: DeterministicMappingResult,
    slack_path: str | Path = "sources/ops_slack_thread.md",
    kb_path: str | Path = "knowledge_base.json",
    cache_path: str | Path = "llm_cache.json",
    batch_size: int = 10,
    force_replay: bool = False,
) -> tuple[list[CaseResolution], KnowledgeBase]:
    kb = KnowledgeBase.load(kb_path)
    slack_thread = Path(slack_path).read_text(encoding="utf-8")
    deps = ResolutionDeps(
        mapping_result=mapping_result,
        slack_thread=slack_thread,
        knowledge_base=kb,
    )

    cache_file = Path(cache_path)
    cache_data: dict[str, Any] = (
        json.loads(cache_file.read_text(encoding="utf-8")) if cache_file.exists() else {"resolutions": {}}
    )
    has_api_key = bool(os.environ.get("OPENAI_API_KEY")) and not force_replay

    all_resolutions: list[CaseResolution] = []
    cases = mapping_result.unresolved_cases

    with logfire.span(
        "stage_2.agentic_resolution",
        total_cases=len(cases),
        batch_size=batch_size,
        mode="live_llm" if has_api_key else "cached_replay",
    ) as span:
        print("\n" + "=" * 80)
        print("[Stage 2: Context-Targeted Agentic Resolution (PydanticAI)]")
        if not has_api_key and cache_data.get("resolutions"):
            print(f"  • Offline / Dry-Run Mode: Replaying {len(cases)} cached model resolutions from '{cache_path}'")
            logfire.info("Replaying cached LLM resolutions from llm_cache.json (dry-run / offline mode)")
            for c in cases:
                if c.case_id in cache_data["resolutions"]:
                    res = CaseResolution.model_validate(cache_data["resolutions"][c.case_id])
                    all_resolutions.append(res)
                    if res.action != "flag_for_clarification":  # an unanswered blocker is not a settled rule
                        for rule in res.learned_rules:
                            kb.upsert(rule)
            print(f"  ✓ Replayed {len(all_resolutions)} decisions instantly (zero API cost).")
        else:
            total_batches = (len(cases) + batch_size - 1) // batch_size
            print(f"  • Live Execution: Routing {len(cases)} unresolved cases across {total_batches} batches to 'openai:gpt-5.6-luna'...")
            for i in range(0, len(cases), batch_size):
                batch_idx = (i // batch_size) + 1
                batch = cases[i : i + batch_size]
                print(f"\n  ▶ [Batch {batch_idx}/{total_batches}] Packaging {len(batch)} ambiguous records with cross-source context:")
                for c in batch:
                    raw = c.raw_record
                    rec_name = raw.get("Name") or raw.get("Account_Holder") or raw.get("Client") or raw.get("page_id", "")[:8]
                    reasons_str = ", ".join(c.reasons[:3])
                    print(f"    - {c.case_id} ({rec_name}) -> {reasons_str}")

                print(f"    Invoking gpt-5.6-luna with structured schema (Batch {batch_idx})... ", end="", flush=True)
                with logfire.span(
                    "resolve_batch",
                    batch_index=i // batch_size,
                    case_ids=[c.case_id for c in batch],
                ):
                    bundles = [build_case_context(c, deps) for c in batch]
                    prompt = (
                        "Resolve each of the following UnresolvedCase items using the Advisor Roster, "
                        "Round 1 Slack Thread, and Cross-Source Context:\n\n"
                        + json.dumps(bundles, indent=2, default=str)
                    )
                    result = resolution_agent.run_sync(prompt, deps=deps)
                    print("Done.")

                    for res in result.output.resolutions:
                        all_resolutions.append(res)
                        cache_data.setdefault("resolutions", {})[res.case_id] = res.model_dump()
                        if res.action != "flag_for_clarification":  # an unanswered blocker is not a settled rule
                            for rule in res.learned_rules:
                                kb.upsert(rule)
                        action_symbol = "✓" if res.action == "auto_apply" else "!"
                        print(f"      {action_symbol} {res.case_id}: action={res.action}, conf={res.confidence:.2f}, prov={res.provenance_source} | {res.evidence[:65]}...")

            cache_file.write_text(json.dumps(cache_data, indent=2), encoding="utf-8")
            print(f"\n  ✓ Successfully resolved {len(all_resolutions)} cases. Cached responses to '{cache_path}'.")

        kb.save(kb_path)
        print(f"  • Updated Knowledge Base: {len(kb.rules)} total learned rules persisted to '{kb_path}'")
        print("=" * 80)
        span.set_attribute("resolved_count", len(all_resolutions))
        span.set_attribute("kb_rules_count", len(kb.rules))
        logfire.info(
            "Stage 2 agentic resolution complete",
            resolved_count=len(all_resolutions),
            kb_rules_count=len(kb.rules),
        )

    return all_resolutions, kb
