import json
import re
from pathlib import Path
from typing import Any
import logfire
import pandas as pd

from knowledge import KnowledgeBase
from mapper import DeterministicMappingResult
from models import (
    Account,
    AccountType,
    CanonicalOutput,
    ClarificationItem,
    Client,
    ClientRole,
    Household,
    HouseholdStatus,
    Interaction,
    InteractionType,
    Provenance,
)
from resolver import CaseResolution


def slugify_id(prefix: str, text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return f"{prefix}_{clean}"


def split_person_name(raw_name: str) -> tuple[str, str]:
    if "," in raw_name:
        last, first = [p.strip() for p in raw_name.split(",", 1)]
        return first, last
    parts = raw_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def normalize_household_name(raw_hh: str | None, fallback_last_name: str) -> str:
    base = (raw_hh or fallback_last_name).strip()
    base = re.sub(r"\s+Household$", "", base, flags=re.IGNORECASE).strip()
    return f"{base} Household"


def build_canonical_output(
    mapping_result: DeterministicMappingResult,
    resolutions: list[CaseResolution],
    kb: KnowledgeBase,
) -> tuple[CanonicalOutput, list[ClarificationItem]]:
    with logfire.span("stage_3.assemble_and_validate") as span:
        res_by_id: dict[str, CaseResolution] = {r.case_id: r for r in resolutions}
        clarifications: list[ClarificationItem] = []

        # Collect clarifications emitted by the agent
        for r in resolutions:
            if r.clarification is not None:
                clarifications.append(r.clarification)

        advisor_by_name = {a.full_name: a.advisor_id for a in mapping_result.advisors}
        advisor_ids = {a.advisor_id for a in mapping_result.advisors}

        STRICT_STATUS_MAP: dict[str, HouseholdStatus] = {
            "Active": "ACTIVE",
            "ACTIVE": "ACTIVE",
            "active": "ACTIVE",
            "Client": "ACTIVE",
            "Legacy": "ACTIVE",
            "Inactive": "INACTIVE",
            "Former": "INACTIVE",
            "Churned": "INACTIVE",
            "Prospect": "PROSPECT",
        }
        STRICT_ACCT_TYPE_MAP: dict[str, AccountType] = {
            "Individual": "INDIVIDUAL",
            "Joint WROS": "JOINT",
            "Joint TIC": "JOINT",
            "Trust-Rev": "TRUST",
            "IRA": "IRA",
            "Rollover IRA": "IRA",
            "Roth IRA": "ROTH_IRA",
            "Corporate": "CORPORATE",
        }
        STRICT_INTERACTION_MAP: dict[str, InteractionType] = {
            "Review": "REVIEW",
            "Annual Review": "REVIEW",
            "QBR": "REVIEW",
            "Check-in": "REVIEW",
            "Prospecting": "PROSPECTING",
            "Intro Call": "PROSPECTING",
            "Discovery": "PROSPECTING",
            "Onboarding": "ONBOARDING",
        }

        # 1. Assemble Clients & group into Households
        clients_out: list[Client] = []
        hh_groups: dict[str, list[dict[str, Any]]] = {}
        client_name_to_hh_id: dict[str, str] = {}

        for raw_c in mapping_result.all_clients_raw:
            case_id = f"client:{raw_c['page_id'][:8]}"
            res = res_by_id.get(case_id)

            # Check if dropped duplicate
            if (res and res.action == "drop_duplicate") or kb.get_rule("duplicate_client", raw_c["Name"]):
                continue

            first_name, last_name = split_person_name(raw_c["Name"])
            hh_name = (
                res.resolved_household_name
                if (res and res.resolved_household_name)
                else normalize_household_name(raw_c.get("Household"), last_name)
            )
            hh_id = slugify_id("hh", hh_name.replace(" Household", ""))
            client_name_to_hh_id[raw_c["Name"]] = hh_id

            # Determine advisor_id for this client row
            raw_adv = raw_c.get("Advisor")
            adv_id = None
            if res and res.resolved_advisor_id and res.resolved_advisor_id in advisor_ids:
                adv_id = res.resolved_advisor_id
            elif raw_adv in advisor_by_name:
                adv_id = advisor_by_name[raw_adv]
            elif raw_adv in advisor_ids:
                adv_id = raw_adv
            else:
                adv_rule = kb.get_rule("advisor_alias", raw_adv)
                if adv_rule and adv_rule.target_value in advisor_ids:
                    adv_id = adv_rule.target_value

            # Determine status
            raw_status = (raw_c.get("Status") or "").strip()
            status: HouseholdStatus = (
                res.resolved_status
                if (res and res.resolved_status)
                else STRICT_STATUS_MAP.get(raw_status, "ACTIVE")
            )

            # Build source_tags (Rule 6: preserve meaningful CRM properties, drop Website)
            tags: list[str] = []
            if raw_status == "Legacy":
                tags.append("lineage:harborline")
            if res and res.added_source_tags:
                for t in res.added_source_tags:
                    if t not in tags:
                        tags.append(t)
            if raw_c.get("Segment"):
                seg = "HNW" if raw_c["Segment"] == "High Net Worth" else raw_c["Segment"]
                tags.append(f"segment:{seg}")
            if raw_c.get("Risk Profile"):
                rp = "Moderate" if raw_c["Risk Profile"] == "3 - Moderate" else raw_c["Risk Profile"]
                tags.append(f"risk_profile:{rp}")
            if raw_c.get("Fee Schedule"):
                fs = "Tier 1" if raw_c["Fee Schedule"] == "tier 1" else raw_c["Fee Schedule"]
                tags.append(f"fee_schedule:{fs}")
            if raw_c.get("Client Since"):
                iso_since = pd.to_datetime(raw_c["Client Since"], format="mixed").strftime("%Y-%m-%d")
                tags.append(f"client_since:{iso_since}")
            if raw_c.get("Referred By"):
                tags.append(f"referred_by:{raw_c['Referred By']}")
            if raw_c.get("Tags"):
                for t in [x.strip() for x in str(raw_c["Tags"]).split(",")]:
                    tags.append(f"tag:{t}")

            prov = [
                Provenance(
                    source="deterministic",
                    rule_or_model="notion_clients_md",
                    confidence=1.0,
                    evidence=f"Clients page {raw_c['page_id'][:8]} ({raw_c['Name']})",
                )
            ]
            if res:
                prov.append(
                    Provenance(
                        source=res.provenance_source,
                        rule_or_model="nevis_ambiguity_resolver",
                        confidence=res.confidence,
                        evidence=res.evidence,
                    )
                )

            hh_groups.setdefault(hh_id, []).append(
                {
                    "raw": raw_c,
                    "res": res,
                    "first_name": first_name,
                    "last_name": last_name,
                    "hh_name": hh_name,
                    "adv_id": adv_id,
                    "status": status,
                    "tags": tags,
                    "prov": prov,
                }
            )

        # Build Households & finalize Client roles
        households_out: list[Household] = []
        valid_hh_ids: set[str] = set()

        for hh_id, members in sorted(hh_groups.items()):
            hh_name = members[0]["hh_name"]
            adv_candidates = [m["adv_id"] for m in members if m["adv_id"]]
            primary_adv_id = adv_candidates[0] if adv_candidates else None

            # Rule 1: One primary advisor per household (required and non-null).
            # If primary_adv_id is None, hold household out of canonical_output (already flagged for Dana)
            if not primary_adv_id:
                logfire.warn("Holding household out of canonical output due to missing primary_advisor_id", hh_id=hh_id, hh_name=hh_name)
                continue

            valid_hh_ids.add(hh_id)
            hh_tags: list[str] = []
            for m in members:
                for t in m["tags"]:
                    if t.startswith(("lineage:", "segment:", "tag:")) and t not in hh_tags:
                        hh_tags.append(t)

            households_out.append(
                Household(
                    household_id=hh_id,
                    household_name=hh_name,
                    primary_advisor_id=primary_adv_id,
                    status=members[0]["status"],
                    as_of_date=None,
                    aum_usd=None,
                    source_tags=hh_tags,
                    provenance=members[0]["prov"],
                )
            )

            for idx, m in enumerate(members):
                role: ClientRole = (
                    m["res"].resolved_client_role
                    if (m["res"] and m["res"].resolved_client_role)
                    else ("PRIMARY" if idx == 0 else "SPOUSE")
                )
                clients_out.append(
                    Client(
                        client_id=f"cli_{m['raw']['page_id'][:8]}",
                        household_id=hh_id,
                        first_name=m["first_name"],
                        last_name=m["last_name"],
                        role=role,
                        source_tags=m["tags"],
                        provenance=m["prov"],
                    )
                )

        # 2. Assemble Accounts (Rule 4: Every account rolls up to a household; Rule 5: USD conversion)
        accounts_out: list[Account] = []
        hh_by_id = {h.household_id: h for h in households_out}

        for raw_a in mapping_result.all_accounts_raw:
            acct_num = raw_a["Account_Number"]
            case_id = f"account:{acct_num}"
            res = res_by_id.get(case_id)
            holder = raw_a["Account_Holder"]

            hh_id = client_name_to_hh_id.get(holder)
            if not hh_id and res and res.resolved_household_name:
                hh_id = slugify_id("hh", res.resolved_household_name.replace(" Household", ""))
            if not hh_id:
                holder_rule = kb.get_rule("account_holder_to_household", holder)
                if holder_rule and holder_rule.target_value:
                    hh_id = slugify_id("hh", holder_rule.target_value.replace(" Household", ""))

            # Rule 4: No orphan accounts in canonical output
            if not hh_id or hh_id not in valid_hh_ids:
                logfire.warn("Skipping orphan or unassigned-advisor account from canonical output", account_id=acct_num, holder=holder, resolved_hh_id=hh_id)
                continue

            curr = raw_a["Currency"]
            mv_usd = float(raw_a["Market_Value"])
            if curr != "USD":
                if res and res.resolved_market_value_usd:
                    mv_usd = res.resolved_market_value_usd
                else:
                    fx_map = {"EUR": 1.08, "CHF": 1.12}
                    mv_usd = round(mv_usd * fx_map.get(curr, 1.0), 2)

            acct_type: AccountType = (
                res.resolved_account_type
                if (res and res.resolved_account_type)
                else STRICT_ACCT_TYPE_MAP.get(raw_a["Account_Type"], "OTHER")
            )

            prov = [
                Provenance(
                    source="deterministic",
                    rule_or_model="custodian_positions_xlsx",
                    confidence=1.0,
                    evidence=f"Account {acct_num} ({holder})",
                )
            ]
            if res:
                prov.append(
                    Provenance(
                        source=res.provenance_source,
                        rule_or_model="nevis_ambiguity_resolver",
                        confidence=res.confidence,
                        evidence=res.evidence,
                    )
                )

            accounts_out.append(
                Account(
                    account_id=acct_num,
                    household_id=hh_id,
                    account_type=acct_type,
                    market_value_usd=mv_usd,
                    currency_original=curr,
                    as_of_date=str(raw_a["As_Of_Date"]),
                    custodian=raw_a["Custodian"],
                    provenance=prov,
                )
            )

        # Roll up AUM and as_of_date to Households (Rule 2 & Rule 3: Unknown != 0; no accounts -> aum_usd = None)
        for acct in accounts_out:
            hh = hh_by_id[acct.household_id]
            hh.aum_usd = round((hh.aum_usd or 0.0) + (acct.market_value_usd or 0.0), 2)
            if hh.as_of_date is None or acct.as_of_date > hh.as_of_date:
                hh.as_of_date = acct.as_of_date

        # 3. Assemble Interactions (Rule 7: Every interaction rolls up to an existing household)
        interactions_out: list[Interaction] = []
        for raw_m in mapping_result.all_interactions_raw:
            page_id = raw_m["page_id"][:8]
            case_id = f"interaction:{page_id}"
            res = res_by_id.get(case_id)
            m_client = raw_m.get("Client")

            hh_id = client_name_to_hh_id.get(m_client)
            if not hh_id and res and res.resolved_household_name:
                hh_id = slugify_id("hh", res.resolved_household_name.replace(" Household", ""))
            if not hh_id:
                alias_rule = kb.get_rule("meeting_client_alias", m_client)
                if alias_rule and alias_rule.target_value:
                    hh_id = client_name_to_hh_id.get(alias_rule.target_value)

            if not hh_id or hh_id not in valid_hh_ids:
                logfire.warn("Skipping orphan or unassigned-household interaction", interaction_id=page_id, client=m_client)
                continue

            raw_att = raw_m.get("Attendee")
            adv_id = None
            if res and res.resolved_advisor_id in advisor_ids:
                adv_id = res.resolved_advisor_id
            elif raw_att in advisor_by_name:
                adv_id = advisor_by_name[raw_att]

            int_type: InteractionType = (
                res.resolved_interaction_type
                if (res and res.resolved_interaction_type)
                else STRICT_INTERACTION_MAP.get(raw_m.get("Type", ""), "OTHER")
            )
            iso_date = pd.to_datetime(raw_m["Date"], format="mixed").strftime("%Y-%m-%d")

            prov = [
                Provenance(
                    source="deterministic",
                    rule_or_model="notion_meetings_md",
                    confidence=1.0,
                    evidence=f"Meeting {page_id} ({raw_m['Name']})",
                )
            ]
            if res:
                prov.append(
                    Provenance(
                        source=res.provenance_source,
                        rule_or_model="nevis_ambiguity_resolver",
                        confidence=res.confidence,
                        evidence=res.evidence,
                    )
                )

            interactions_out.append(
                Interaction(
                    interaction_id=f"int_{page_id}",
                    household_id=hh_id,
                    interaction_type=int_type,
                    interaction_date=iso_date,
                    advisor_id=adv_id,
                    summary=raw_m.get("Notes"),
                    provenance=prov,
                )
            )

        # 4. Post-Mapping Validation Checks (catches plausible-but-wrong results & cross-record conflicts)
        with logfire.span("post_mapping_validation"):
            # Check for spouse Fee Schedule / Risk Profile conflicts within the same household
            for hh_id, members in hh_groups.items():
                if len(members) > 1:
                    fees = {m["raw"].get("Fee Schedule") for m in members if m["raw"].get("Fee Schedule")}
                    risks = {m["raw"].get("Risk Profile") for m in members if m["raw"].get("Risk Profile")}
                    if len(fees) > 1 or len(risks) > 1:
                        member_desc = ", ".join(
                            f"{m['raw']['Name']} (Risk={m['raw'].get('Risk Profile')}, Fee={m['raw'].get('Fee Schedule')})"
                            for m in members
                        )
                        clarifications.append(
                            ClarificationItem(
                                id=f"val_spouse_conflict_{hh_id}",
                                category="Household Attribute Conflict",
                                trigger=f"Conflicting Risk Profile / Fee Schedule between members of {members[0]['hh_name']}",
                                evidence=member_desc,
                                candidate_options=[
                                    f"Use primary contact ({members[0]['raw']['Name']}) attributes at household level",
                                    "Keep Fee Schedule and Risk Profile strictly at the individual client/account level",
                                ],
                                proposed_default="Preserve individual values on each client record and use primary contact's profile at the household level",
                                question_for_dana=f"In {members[0]['hh_name']}, the two spouses have different Risk Profiles and Fee Schedules ({member_desc}). Which schedule/profile governs the household, and what bps rates do 'Tier 1', 'Tier 2', and 'See LOE' represent?",
                            )
                        )

            # Assert all 7 Canonical Rules hold on canonical_output
            for h in households_out:
                assert h.primary_advisor_id in advisor_ids, f"Rule 1 violation on {h.household_id}"
                hh_accts = [a for a in accounts_out if a.household_id == h.household_id]
                if not hh_accts:
                    assert h.aum_usd is None, f"Rule 3 violation (unknown != 0) on {h.household_id}"
                else:
                    assert abs((h.aum_usd or 0.0) - sum(a.market_value_usd or 0.0 for a in hh_accts)) < 0.01, f"Rule 2 violation on {h.household_id}"
            for a in accounts_out:
                assert a.household_id in valid_hh_ids, f"Rule 4 violation on {a.account_id}"
                assert a.market_value_usd is not None, f"Rule 5 violation on {a.account_id}"
            for i in interactions_out:
                assert i.household_id in valid_hh_ids, f"Rule 7 violation on {i.interaction_id}"

        output = CanonicalOutput(
            advisors=mapping_result.advisors,
            households=households_out,
            clients=clients_out,
            accounts=accounts_out,
            interactions=interactions_out,
        )

        span.set_attribute("canonical_households", len(households_out))
        span.set_attribute("canonical_clients", len(clients_out))
        span.set_attribute("canonical_accounts", len(accounts_out))
        span.set_attribute("canonical_interactions", len(interactions_out))
        span.set_attribute("clarifications_count", len(clarifications))

        return output, clarifications

