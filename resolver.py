import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
import logfire
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from knowledge import KnowledgeBase, KnowledgeRule
from mapper import DeterministicMappingResult, UnresolvedCase
from models import (
    AccountType,
    ClarificationItem,
    ClientRole,
    HouseholdStatus,
    InteractionType,
)

load_dotenv(".env.local")
load_dotenv()


class CaseResolution(BaseModel):
    case_id: str
    action: Literal["auto_apply", "drop_duplicate", "flag_for_clarification"]
    confidence: float = Field(ge=0.0, le=1.0)
    provenance_source: Literal["slack_knowledge", "llm"]
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
    clarification: ClarificationItem | None = None


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
    instructions=(
        "You are a Forward Deployed Engineer agent mapping a wealth management firm's source data "
        "(Notion CRM exports + custodian positions spreadsheet + advisor roster) into the Nevis Canonical Data Model.\n\n"
        "### Nevis Canonical Rules\n"
        "1. One primary advisor per household (required and non-null). Never guess an advisor from a secondary/service role if the stakeholder forbade it.\n"
        "2. AUM is market value in USD. Household AUM is the sum of its accounts' market_value_usd.\n"
        "3. Unknown != zero. A household with no known accounts has AUM null, not 0.\n"
        "4. Every account rolls up to exactly one household. No orphan accounts in canonical output; if an account holder has no match in CRM, flag it.\n"
        "5. Currency: non-USD amounts must be converted to market_value_usd using quarter-end FX rates (e.g. Q2 2025: 1 EUR = 1.08 USD, 1 CHF = 1.12 USD); flag any currency not yet confirmed by operations.\n"
        "6. Fields with no first-class home: preserve business-meaningful attributes/lineage as `added_source_tags` (e.g. 'lineage:<source>'), drop irrelevant fields, and flag genuine contradictions (e.g. Active status with Deceased tag, or conflicting attributes across duplicate records).\n"
        "7. Every interaction rolls up to an existing household. Never mint a new household from an interaction; if the interaction's client is not in the CRM yet, flag it as an orphan.\n\n"
        "### How to Resolve Each UnresolvedCase\n"
        "- Inspect `reasons`, `raw_record`, `related_context` (CRM notes, custodian accounts, meetings), the Advisor Roster, and the Round 1 Onboarding Slack Thread.\n"
        "- If the Round 1 Slack Thread settles how to handle the case:\n"
        "  * Set `provenance_source='slack_knowledge'` and `confidence >= 0.95`.\n"
        "  * Do NOT re-ask what the stakeholder already answered.\n"
        "- If the Notion Markdown `Notes` or name/household matching clearly resolves an entity link (e.g. a spouse's missing household, an abbreviated advisor name, a joint/trust account holder, or a duplicate CRM import):\n"
        "  * Set `action='auto_apply'` (or `action='drop_duplicate'` for a confirmed duplicate record).\n"
        "  * Normalize household names to '<LastName> Household'.\n"
        "- Whenever you resolve a mapping that should apply automatically on future syncs, emit a `KnowledgeRule` in `learned_rules`:\n"
        "  * `rule_type='status_map'` (e.g. source_value='Legacy' -> target_value='ACTIVE', extra_tags=['lineage:harborline'])\n"
        "  * `rule_type='advisor_alias'` (e.g. source_value='P. Raman' -> target_value='ADV-001')\n"
        "  * `rule_type='departed_staff'` (when Slack says a staff member left the firm)\n"
        "  * `rule_type='duplicate_client'` (when Slack/notes confirm a duplicate client row to collapse)\n"
        "  * `rule_type='household_link'` (when a note links a client with a blank Household to an existing household)\n"
        "  * `rule_type='account_holder_to_household'` (when a joint/trust/nickname account holder maps to a household)\n"
        "  * `rule_type='meeting_client_alias'` (when a meeting client nickname maps to a full CRM client name)\n"
        "  * `rule_type='fx_rate'` (when converting a non-USD currency confirmed in Slack)\n"
        "  * `rule_type='ignored_field'` (when Slack confirms a column like Service Rep or Cost_Basis is not used for canonical mapping)\n"
        "- If a case has a genuine ambiguity, missing required advisor, orphan account/interaction, stale active balance date, or a note explicitly saying 'flag for ops':\n"
        "  * Set `action='flag_for_clarification'` and populate `clarification` with a scoped, client-ready question for Dana (with trigger, evidence, candidate_options, and proposed_default)."
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
    batch_size: int = 10,
) -> tuple[list[CaseResolution], KnowledgeBase]:
    kb = KnowledgeBase.load(kb_path)
    slack_thread = Path(slack_path).read_text(encoding="utf-8")
    deps = ResolutionDeps(
        mapping_result=mapping_result,
        slack_thread=slack_thread,
        knowledge_base=kb,
    )

    all_resolutions: list[CaseResolution] = []
    cases = mapping_result.unresolved_cases

    with logfire.span("stage_2.agentic_resolution", total_cases=len(cases), batch_size=batch_size) as span:
        for i in range(0, len(cases), batch_size):
            batch = cases[i : i + batch_size]
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
                for res in result.output.resolutions:
                    all_resolutions.append(res)
                    for rule in res.learned_rules:
                        kb.upsert(rule)

        kb.save(kb_path)
        span.set_attribute("resolved_count", len(all_resolutions))
        span.set_attribute("kb_rules_count", len(kb.rules))
        logfire.info(
            "Stage 2 agentic resolution complete",
            resolved_count=len(all_resolutions),
            kb_rules_count=len(kb.rules),
        )

    return all_resolutions, kb
