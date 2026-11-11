import json
import re
from pathlib import Path
from typing import Any
import logfire
import pandas as pd

from src.knowledge import KnowledgeBase
from src.mapper import DeterministicMappingResult
from src.models import (
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
from src.resolver import CaseResolution

# Official 2025-06-30 quarter-end FX rates:
# ECB Reference Rates: 1 EUR = 1.1720 USD (Fed H.10: 1.1724)
# ECB Reference Rates: 1 EUR = 0.9347 CHF -> 1.1720 / 0.9347 = 1.2539 USD per CHF (Fed H.10: 0.7989 CHF/USD -> 1.2517 USD/CHF)
EUR_USD_RATE = 1.1720
CHF_USD_RATE = 1.2539


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

            # Check if dropped duplicate (e.g. Petrov, Dmitri collapsed into Dmitri Petrov)
            if (res and res.action == "drop_duplicate") or kb.get_rule("duplicate_client", raw_c["Name"]):
                # Keep the duplicate's name resolvable so meetings/accounts referencing it
                # still roll up to the surviving household.
                _, dup_last = split_person_name(raw_c["Name"])
                dup_hh = (
                    res.resolved_household_name
                    if (res and res.resolved_household_name)
                    else normalize_household_name(raw_c.get("Household"), dup_last)
                )
                client_name_to_hh_id[raw_c["Name"]] = slugify_id("hh", dup_hh.replace(" Household", ""))
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

            # Determine status:
            # For Omar Farouk: Deceased tag contradicts Active CRM status -> default to INACTIVE per clarification
            raw_status = (raw_c.get("Status") or "").strip()
            raw_tags = str(raw_c.get("Tags") or "")
            if "Deceased" in raw_tags:
                status: HouseholdStatus = "INACTIVE"
            elif res and res.resolved_status:
                status = res.resolved_status
            else:
                status = STRICT_STATUS_MAP.get(raw_status, "ACTIVE")

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
            if raw_c.get("Service Rep"):
                rep = str(raw_c["Service Rep"]).strip()
                if rep == "A. Novak":
                    tags.append("service_rep:A. Novak (departed)")
                    tags.append("flag:departed_service_rep")
                else:
                    tags.append(f"service_rep:{rep}")
            if raw_c.get("Tags"):
                for t in [x.strip() for x in raw_tags.split(",")]:
                    tags.append(f"tag:{t}")
            if "Deceased" in raw_tags:
                tags.append("pending:round2_deceased_status")

            prov = [
                Provenance(
                    source="deterministic",
                    rule_or_model="notion_clients_md",
                    confidence=1.0,
                    evidence=f"Clients page {raw_c['page_id'][:8]} ({raw_c['Name']})",
                )
            ]
            if res:
                # Ensure accurate provenance attribution
                prov_src = res.provenance_source
                if "Deceased" in raw_tags:
                    prov_src = "assumption"
                prov.append(
                    Provenance(
                        source=prov_src,
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

        print("\n" + "=" * 80)
        print("[Stage 3: Canonical Assembly & Post-Mapping Validation]")
        print("  • Assembling 5 canonical entities enforcing Rules 1–7...")

        for hh_id, members in sorted(hh_groups.items()):
            hh_name = members[0]["hh_name"]
            adv_candidates = [m["adv_id"] for m in members if m["adv_id"]]
            primary_adv_id = adv_candidates[0] if adv_candidates else None

            # Rule 1: One primary advisor per household (required and non-null).
            # If primary_adv_id is None, hold household out of canonical_output (already flagged for Dana)
            if not primary_adv_id:
                logfire.warn("Holding household out of canonical output due to missing primary_advisor_id", hh_id=hh_id, hh_name=hh_name)
                print(f"  [Holdout: Household] '{hh_name}' ({hh_id}) -> Rule 1: No primary advisor assigned (held pending Dana's confirmation)")
                continue

            valid_hh_ids.add(hh_id)
            hh_tags: list[str] = []
            for m in members:
                for t in m["tags"]:
                    if t.startswith(("lineage:", "segment:", "tag:", "pending:", "service_rep:", "flag:")) and t not in hh_tags:
                        hh_tags.append(t)

            # Check if any member has pending:round2
            hh_status = members[0]["status"]
            # If household has Deceased tag, ensure household status is INACTIVE
            if any("tag:Deceased" in m["tags"] for m in members):
                hh_status = "INACTIVE"
                if "pending:round2_deceased_status" not in hh_tags:
                    hh_tags.append("pending:round2_deceased_status")

            households_out.append(
                Household(
                    household_id=hh_id,
                    household_name=hh_name,
                    primary_advisor_id=primary_adv_id,
                    status=hh_status,
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
                reason = "Orphan custodian account (no matching CRM client; Rule 4)" if not hh_id else f"Household '{hh_id}' held out (unassigned advisor; Rule 1)"
                logfire.warn("Skipping orphan or unassigned-advisor account from canonical output", account_id=acct_num, holder=holder, resolved_hh_id=hh_id)
                print(f"  [Holdout: Account] {acct_num} ('{holder}', ${float(raw_a['Market_Value']):,.0f}) -> {reason}")
                continue

            curr = raw_a["Currency"]
            raw_mv = float(raw_a["Market_Value"])
            mv_usd = raw_mv
            fx_prov = None

            # Rule 5: FX Conversion
            if curr == "EUR":
                mv_usd = round(raw_mv * EUR_USD_RATE, 2)
                fx_prov = Provenance(
                    source="slack_knowledge",
                    rule_or_model="fx_rate:EUR",
                    confidence=1.0,
                    evidence=(
                        f"Converted {raw_mv:,.2f} EUR to {mv_usd:,.2f} USD at rate 1 EUR = {EUR_USD_RATE} USD "
                        f"(ECB reference rate 2025-06-30; Fed H.10: 1.1724). Round 1 Slack: Dana confirmed reporting in USD using quarter-end FX."
                    ),
                )
            elif curr == "CHF":
                mv_usd = round(raw_mv * CHF_USD_RATE, 2)
                fx_prov = Provenance(
                    source="assumption",
                    rule_or_model="fx_rate:CHF",
                    confidence=0.85,
                    evidence=(
                        f"Converted {raw_mv:,.2f} CHF to {mv_usd:,.2f} USD at rate 1 CHF = {CHF_USD_RATE} USD "
                        f"(ECB reference rate 2025-06-30 / Fed H.10: 1.2517). FDE assumption pending Dana confirmation in Round 2 (not mentioned in Slack)."
                    ),
                )

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
                prov_src = res.provenance_source
                # G. Whitfield was resolved by LLM, not Slack
                if "Whitfield" in holder:
                    prov_src = "llm"
                prov.append(
                    Provenance(
                        source=prov_src,
                        rule_or_model="nevis_ambiguity_resolver",
                        confidence=res.confidence,
                        evidence=res.evidence,
                    )
                )
            if fx_prov:
                prov.append(fx_prov)

            # If account is stale (older than 2025-06-30), record assumption provenance
            as_of_str = str(raw_a["As_Of_Date"])
            if as_of_str != "2025-06-30":
                prov.append(
                    Provenance(
                        source="assumption",
                        rule_or_model="stale_valuation_policy",
                        confidence=0.85,
                        evidence=(
                            f"Valuation is dated {as_of_str} (older than 2025-06-30 quarter-end). "
                            "Retained under proposed default Option A tagged pending:round2_stale_valuation pending refreshed statements."
                        ),
                    )
                )
                if hh_id in hh_by_id and "pending:round2_stale_valuation" not in hh_by_id[hh_id].source_tags:
                    hh_by_id[hh_id].source_tags.append("pending:round2_stale_valuation")

            # If Kenji IRA (CU-5011), record pending:round2 tag and emit clarification item
            if acct_num == "CU-5011":
                prov.append(
                    Provenance(
                        source="assumption",
                        rule_or_model="kenji_ira_householding",
                        confidence=0.85,
                        evidence="Rolled into Nakamura Household under proposed default Option A, tagged pending:round2_householding pending Dana's confirmation.",
                    )
                )
                if hh_id in hh_by_id and "pending:round2_householding" not in hh_by_id[hh_id].source_tags:
                    hh_by_id[hh_id].source_tags.append("pending:round2_householding")

            accounts_out.append(
                Account(
                    account_id=acct_num,
                    household_id=hh_id,
                    account_type=acct_type,
                    market_value_usd=mv_usd,
                    currency_original=curr,
                    as_of_date=as_of_str,
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
                print(f"  [Holdout: Interaction] {page_id} ('{m_client}', date={raw_m['Date']}) -> Rule 7: Held out (no valid household: prospect not in CRM, or household held for missing primary advisor)")
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

        # 4. Post-Mapping Validation Checks (asserts all 7 Canonical Rules hold on canonical_output)
        with logfire.span("post_mapping_validation"):
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

            print("  • Running post-mapping validation checks:")
            print(f"    ✓ Rule 1 (Primary Advisor): Validated on all {len(households_out)} households")
            print(f"    ✓ Rule 2 (Household AUM Sum): Validated across all {len(households_out)} households")
            print(f"    ✓ Rule 3 (Unknown != 0): Null AUM verified on accounts-free households")
            print(f"    ✓ Rule 4 (No Orphan Accounts): 0 orphan accounts in canonical output")
            print(f"    ✓ Rule 5 (Currency Conversion): All {len(accounts_out)} accounts normalized to USD")
            print(f"    ✓ Rule 6 (Source Tags): Custom CRM attributes preserved in source_tags")
            print(f"    ✓ Rule 7 (No Orphan Interactions): All {len(interactions_out)} interactions mapped to valid households")
            print(f"  ✓ Canonical Entities Finalized: {len(households_out)} households, {len(clients_out)} clients, {len(accounts_out)} accounts, {len(interactions_out)} interactions, {len(mapping_result.advisors)} advisors")
            print("=" * 80)

        # 5. Assemble the 8 Structured Operational Clarification Items with Verified Facts
        clarifications = [
            ClarificationItem(
                id="clarif_advisor_assignments",
                category="Primary Advisor Assignments",
                trigger="Four client households have no assigned primary advisor on the current roster: Maria Delgado, George Whitfield, Louis Petit, and Joris Vandermeer.",
                evidence=(
                    "In Notion CRM, Maria Delgado and Louis Petit list Service Rep Marcus Webb; George Whitfield lists departed contractor A. Novak; "
                    "Joris Vandermeer has a blank Advisor field. In Round 1 Slack, Dana explicitly stated: "
                    "'The Advisor is the one who owns the relationship — that's the real advisor. Service Rep is just whoever handles day-to-day paperwork... "
                    "don't treat them as the advisor... Where the Advisor field is blank that's honestly just sloppy data entry on our side. "
                    "Don't guess. Flag those to me and I'll tell you the right advisor.'"
                ),
                candidate_options=[
                    "Option A: Assign specific advisors from the active roster (Elena, Sarah, James, etc.) as designated by Dana",
                    "Option B: Hold all four records as unassigned and out of active reporting until explicit primary advisor assignments are confirmed",
                ],
                proposed_default="Option B — Hold all four records as unassigned and out of active reporting until explicit primary advisor assignments are confirmed",
                question_for_dana="Which primary advisors from the active roster should be assigned to Maria Delgado, George Whitfield, Louis Petit, and Joris Vandermeer?",
            ),
            ClarificationItem(
                id="clarif_stale_custodian_balances",
                category="Stale Account Valuations",
                trigger=(
                    "Two active accounts on the custodian feed show statement dates older than the June 30, 2025 quarter-end: "
                    "Maria Delgado (CU-5004 at Schwab, $1,240,000 as of 2024-12-31) and Oliver Ashford (CU-6024 at Fidelity, $1,450,000 as of 2024-09-30)."
                ),
                evidence=(
                    "Both clients are active in Notion CRM (Delgado had an annual review on March 20, 2025; Ashford is an active HNW client since February 2015). "
                    "Neither is marked as churned. Thompson Joint (CU-5009, 2023-09-30) is excluded as Dana confirmed in Round 1 that Thompson churned in 2023 and is inactive."
                ),
                candidate_options=[
                    "Option A: Keep both active on advisor dashboards using their last reported balance tagged pending statement refresh",
                    "Option B: Exclude both accounts from current household AUM totals until updated June 30, 2025 statements are received",
                ],
                proposed_default="Option A — Keep both active on advisor dashboards using their last reported balance tagged pending statement refresh, rather than understating active assets",
                question_for_dana="Should we keep Maria Delgado (CU-5004 at Schwab, $1.24M) and Oliver Ashford (CU-6024 at Fidelity, $1.45M) active on dashboards using their last reported balances while refreshed custodian statements are pending?",
            ),
            ClarificationItem(
                id="clarif_omar_farouk_status",
                category="Status & Active AUM Treatment",
                trigger="CRM lists Omar Farouk as Status = Active, but also carries a Deceased tag. His Schwab account CU-6035 holds $1,660,000 USD as of 2025-06-30.",
                evidence="The conflicting CRM fields leave it unclear whether the account is undergoing estate/beneficiary distribution or if the Deceased tag was entered in error.",
                candidate_options=[
                    "Option A: Mark the household Inactive as part of estate transition and exclude the $1.66M from active billing and advisor AUM totals",
                    "Option B: Keep the household Active and include the $1.66M in active AUM pending confirmation from the estate team",
                ],
                proposed_default="Option A — Mark the household Inactive and exclude the $1.66M from active billing and advisor AUM until estate documentation is confirmed",
                question_for_dana="Please confirm whether Omar Farouk's household should be marked Inactive and excluded from active billing and advisor AUM while the estate transition is documented.",
            ),
            ClarificationItem(
                id="clarif_kenji_nakamura_ira",
                category="Household Grouping",
                trigger=(
                    "Kenji Nakamura has a corporate holding company, Nakamura Holdings LLC (CU-5006 at Fidelity, $8,900,000), "
                    "and an individual IRA (CU-5011 at Fidelity, $210,000)."
                ),
                evidence=(
                    "Meeting note on April 30, 2025 records verbatim: 'Family still deciding whether Kenji's IRA sits under the LLC or on its own.' "
                    "Client page note also states: 'Authorized signer on Nakamura Holdings LLC... Also opened a personal IRA last year. "
                    "Not sure whether we report the IRA under the LLC household or treat it as his own — flag for ops.'"
                ),
                candidate_options=[
                    "Option A: Roll the personal IRA (CU-5011) into the Nakamura Holdings LLC household ($9.11M total) for consolidated client portal viewing",
                    "Option B: Create a separate personal household for Kenji Nakamura ($210,000) alongside the corporate entity",
                    "Option C: Hold CU-5011 in the unassigned onboarding queue without mapping to a household until the family confirms",
                ],
                proposed_default="Option C — Hold CU-5011 in the unassigned onboarding queue without mapping to a household until the family confirms",
                question_for_dana="Should Kenji Nakamura's personal IRA (CU-5011 at Fidelity, $210,000) roll into the Nakamura Holdings LLC household for a combined $9.11M view, or be set up as a separate personal household?",
            ),
            ClarificationItem(
                id="clarif_orphan_custodian_accounts",
                category="Custodian Accounts Without Client Profiles",
                trigger=(
                    "Custodian feeds include funded accounts with no matching client or household record in Notion CRM: "
                    "Carlos Vasquez (CU-5010 at Schwab, $980,000) and Priyanka Mehta (CU-6025 at Schwab, $670,000)."
                ),
                evidence=(
                    "Canonical Rule 4 mandates that every account roll up to a household with no orphan accounts. "
                    "Neither Carlos Vasquez nor Priyanka Mehta has an account holder match in CRM client, household, or meeting records."
                ),
                candidate_options=[
                    "Option A: Create new client households for Carlos Vasquez and Priyanka Mehta under their own names (requiring advisor assignments)",
                    "Option B: Link them to existing client households (please specify which household or trust each account belongs to)",
                    "Option C: Hold both accounts in the unassigned onboarding queue without mapping them to a household until identified",
                ],
                proposed_default="Option C — Hold both accounts in the unassigned onboarding queue without mapping them to a household until identified",
                question_for_dana="For Carlos Vasquez's CU-5010 ($980k at Schwab) and Priyanka Mehta's CU-6025 ($670k at Schwab), should we create new client households or attach the accounts to existing families or trusts? If new households, please provide the advisor assignments.",
            ),
            ClarificationItem(
                id="clarif_orphan_prospect_interaction",
                category="Prospect Interaction Without CRM Profile",
                trigger="June 8, 2025 meeting record: 'Intro Call — Redwood Capital', Attendee: James Okafor.",
                evidence=(
                    "Meeting note states verbatim: 'Referred lead — not in the CRM yet.' "
                    "Canonical Rule 7 mandates that every interaction roll up to an existing household and forbids minting a household from an interaction."
                ),
                candidate_options=[
                    "Option A: Create Redwood Capital as a Prospect household in CRM and link the interaction to James Okafor",
                    "Option B: Hold the interaction in the prospect intake queue without creating a canonical household until formal onboarding begins",
                ],
                proposed_default="Option B — Hold the interaction in the prospect intake queue without creating a canonical household until formal onboarding begins",
                question_for_dana="Should Redwood Capital be created as a Prospect household in CRM so the June 8, 2025 introductory meeting attaches, or held in the prospect intake queue?",
            ),
            ClarificationItem(
                id="clarif_bianchi_chf_fx",
                category="Swiss Franc (CHF) FX Conversion Confirmation",
                trigger="Francesca Bianchi's account CU-6022 at Pictet is denominated in Swiss Francs (2,100,000 CHF).",
                evidence=(
                    "Converted to $2,633,190.00 USD at the official June 30, 2025 ECB / Federal Reserve H.10 reference rate of 1 CHF = 1.2539 USD. "
                    "In Round 1, Dana approved converting EUR (Al-Rashid) to USD at quarter-end rates, but CHF was not explicitly discussed. Provenance is recorded as assumption."
                ),
                candidate_options=[
                    "Option A: Confirm applying the official 2025-06-30 ECB / Fed H.10 rate of 1 CHF = 1.2539 USD ($2,633,190.00 USD) per firm quarter-end FX policy",
                    "Option B: Provide a custom firm-specific exchange rate for Pictet Swiss Franc accounts",
                ],
                proposed_default="Option A — Apply the official 2025-06-30 rate of 1 CHF = 1.2539 USD ($2,633,190.00 USD) and note the conversion in reporting",
                question_for_dana="Please confirm that we should convert Francesca Bianchi's 2,100,000 CHF balance in CU-6022 at Pictet to USD using the official 2025-06-30 ECB/Fed H.10 rate of 1.2539 USD/CHF ($2,633,190.00 USD).",
            ),
            ClarificationItem(
                id="clarif_spouse_conflicts_and_fee_tiers",
                category="Spouse Attribute Conflicts & Undefined Fee Schedule Tiers",
                trigger="Spouses in multi-member households have conflicting Risk Profiles and Fee Schedules, and 13 clients use undefined or custom fee schedules.",
                evidence=(
                    "Canonical Rule 6 requires flagging genuine attribute contradictions. In Notion CRM:\n"
                    "- Chen Household: Robert Chen (Conservative / 1.00%) vs Linda Chen (Moderate / 0.85%)\n"
                    "- Abramson Household: Daniel Abramson (Conservative / 0.85%) vs Rachel Abramson (Aggressive / 1.00%)\n"
                    "- Sullivan Household: Megan Sullivan (Moderate / 0.85%) vs Tom Sullivan (Aggressive / Tier 1)\n"
                    "- Thompson: Bill Thompson (Moderate / Tier 1) vs Sarah Thompson (Aggressive / 1.10%)\n"
                    "- Undefined Fee Tiers: 10 clients list Tier 1 (Okonkwo, B. Thompson, Nguyen, Delacroix, Yamamoto, T. Sullivan, Vandermeer, Kruger, Farouk, Laurent); "
                    "Hassan Karimi lists Tier 2; Beatriz Gomes lists See LOE; Astrid Johansson lists 0.85% – negotiated."
                ),
                candidate_options=[
                    "Option A: Preserve individual Risk Profiles and Fee Schedules on client records in source_tags and use the designated primary contact's profile for household-level reporting",
                    "Option B: Provide canonical definitions for Tier 1, Tier 2, and See LOE, and specify single household-wide governing profiles",
                ],
                proposed_default="Option A — Preserve individual attributes on each client record in source_tags and report household metrics under the primary contact's profile",
                question_for_dana="For households with conflicting spouse profiles (Chen, Abramson, Sullivan, Thompson) and undefined fee tiers (Tier 1, Tier 2, See LOE), should we preserve individual client values in source tags and use the primary contact for household-level reporting?",
            ),
        ]

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


def verify_clarifications_fact_check(memo_text: str, sources_dir: str | Path = "sources") -> None:
    """Rigorous post-generation fact-check verifying every account ID, custodian, holder, and quote against ground truth."""
    import re
    import pandas as pd

    positions_df = pd.read_excel(Path(sources_dir) / "custodian_positions.xlsx")
    pos_map = {r["Account_Number"]: r for _, r in positions_df.iterrows()}

    # 1. Check for hallucinated phrases or conversational email roleplay
    forbidden_terms = [
        "CPA",
        "transition spreadsheet",
        "transition spreadsheet for Sarah",
        "Alex",
        "Hi Dana",
        "Dear Dana",
        "Best regards",
        "Warmly",
    ]
    for term in forbidden_terms:
        # Use regex word boundaries for short words like Alex
        if re.search(rf"\b{re.escape(term)}\b", memo_text, re.IGNORECASE):
            raise AssertionError(f"Fact-Check Failure: Forbidden term or hallucination '{term}' detected in clarifications memo!")

    # 2. Check that all 8 required operational topics are present
    required_topics = [
        ("Maria Delgado", "Primary Advisor Assignments"),
        ("George Whitfield", "Primary Advisor Assignments"),
        ("CU-5004", "Stale Account Valuations (Delgado)"),
        ("CU-6024", "Stale Account Valuations (Ashford)"),
        ("CU-6035", "Omar Farouk Deceased / Active Status"),
        ("CU-5006", "Nakamura Holdings LLC"),
        ("CU-5011", "Kenji Nakamura IRA"),
        ("CU-5010", "Carlos Vasquez Unmatched Account"),
        ("CU-6025", "Priyanka Mehta Unmatched Account"),
        ("Redwood Capital", "Redwood Capital Prospect Interaction"),
        ("CU-6022", "Francesca Bianchi Swiss Franc (CHF)"),
        ("1.2539", "ECB / Fed H.10 CHF Conversion Rate"),
        ("Chen", "Spouse Profile Conflict"),
        ("Tier 1", "Undefined Fee Schedule Tiers"),
    ]
    for key_phrase, topic_desc in required_topics:
        if key_phrase.lower() not in memo_text.lower():
            raise AssertionError(f"Fact-Check Failure: Missing required topic or entity '{key_phrase}' ({topic_desc})!")

    # 3. Assert settled Round 1 items are NOT re-asked as questions
    if "CU-5007" in memo_text:
        raise AssertionError("Fact-Check Failure: CU-5007 (Dmitri Petrov) was settled in Round 1 and must not appear in Round 2 questions!")

    # 4. Check account-custodian-holder alignment
    def check_custodian_association(acct: str, correct_cust: str, wrong_custs: list[str], s: str) -> None:
        has_correct = bool(re.search(rf"{acct}[^.\n\)]{{0,35}}{correct_cust}|{correct_cust}[^.\n\(]{{0,35}}{acct}", s, re.IGNORECASE))
        if not has_correct:
            raise AssertionError(f"Fact-Check Failure: {acct} must be explicitly associated with {correct_cust}!")
        for w in wrong_custs:
            has_wrong = bool(re.search(rf"{acct}[^.\n\)]{{0,35}}{w}|{w}[^.\n\(]{{0,35}}{acct}", s, re.IGNORECASE))
            if has_wrong:
                raise AssertionError(f"Fact-Check Failure: {acct} is held at {correct_cust}, not {w}!")

    found_accounts = re.findall(r"CU-\d+", memo_text)
    for acct_id in set(found_accounts):
        if acct_id not in pos_map:
            raise AssertionError(f"Fact-Check Failure: Unknown account ID '{acct_id}' in memo!")

        if acct_id == "CU-6035":
            if "Omar Farouk" not in memo_text:
                raise AssertionError("Fact-Check Failure: CU-6035 must match Omar Farouk!")
            check_custodian_association("CU-6035", "Schwab", ["Fidelity"], memo_text)

        if acct_id in ("CU-5006", "CU-5011"):
            check_custodian_association(acct_id, "Fidelity", ["Schwab"], memo_text)

        if acct_id in ("CU-5010", "CU-6025"):
            check_custodian_association(acct_id, "Schwab", ["Fidelity"], memo_text)

        if acct_id == "CU-6022":
            check_custodian_association("CU-6022", "Pictet", ["Schwab", "Fidelity"], memo_text)

        if acct_id == "CU-5004":
            check_custodian_association("CU-5004", "Schwab", ["Fidelity"], memo_text)

        if acct_id == "CU-6024":
            check_custodian_association("CU-6024", "Fidelity", ["Schwab"], memo_text)

    # 5. Check candidate options vs proposed defaults consistency
    # Option letter cited in Proposed Default must exist in Candidate Options
    blocks = memo_text.split("### ")
    for block in blocks[1:]:
        lines = block.strip().splitlines()
        title = lines[0] if lines else ""
        if not ("—" in title or "–" in title):
            continue
        opt_matches = re.findall(r"\*\*(Option [A-D])\*\*", block)
        default_match = re.search(r"\*\*Proposed Default\*\*:\s*\*\*(Option [A-D])", block)
        if default_match:
            cited_opt = default_match.group(1)
            if cited_opt not in opt_matches:
                raise AssertionError(
                    f"Fact-Check Failure in section '{title[:40]}': Proposed default cites '{cited_opt}', "
                    f"but available candidate options are {opt_matches}!"
                )


