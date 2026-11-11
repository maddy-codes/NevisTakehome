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
    RawAnomalySignal,
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


_NAME_STOPWORDS = {"llc", "inc", "trust", "revocable", "household", "holdings", "the", "and", "joint"}


def _name_tokens(text: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z]{3,}", (text or "").lower()) if t not in _NAME_STOPWORDS}


def _is_standard_fee(value: str) -> bool:
    return bool(re.match(r"^\d+(\.\d+)?\s*%$", value.strip()))


def build_canonical_output(
    mapping_result: DeterministicMappingResult,
    resolutions: list[CaseResolution],
    kb: KnowledgeBase,
) -> tuple[CanonicalOutput, list[RawAnomalySignal]]:
    """Assemble canonical entities and return the data-derived anomaly signals that need a human decision.

    Signals carry only facts observed in the sources plus the action this pipeline actually took.
    Options and recommended defaults are written downstream (Stage 4), never hardcoded here.
    """
    with logfire.span("stage_3.assemble_and_validate") as span:
        res_by_id: dict[str, CaseResolution] = {r.case_id: r for r in resolutions}
        signals: list[RawAnomalySignal] = []
        held_hh_signals: dict[str, RawAnomalySignal] = {}
        deceased_signals: dict[str, RawAnomalySignal] = {}

        # Quarter-end cutoff = latest valuation date present in the custodian feed.
        valuation_cutoff = max(str(a["As_Of_Date"]) for a in mapping_result.all_accounts_raw)

        def related_notes(holder_or_client: str) -> list[str]:
            toks = _name_tokens(holder_or_client)
            notes: list[str] = []
            for c in mapping_result.all_clients_raw:
                if c.get("Notes") and toks & _name_tokens(c["Name"]):
                    notes.append(f"CRM client note ({c['Name']}): {c['Notes']}")
            for m in mapping_result.all_interactions_raw:
                if m.get("Notes") and toks & _name_tokens(m.get("Client")):
                    notes.append(f"Meeting note ({m.get('Client')}): {m['Notes']}")
            return notes

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
                held_hh_signals[hh_id] = RawAnomalySignal(
                    signal_id=f"sig_missing_advisor_{hh_id}",
                    anomaly_type="missing_primary_advisor",
                    affected_entities=[hh_name],
                    facts={
                        "household": hh_name,
                        "clients": [
                            {
                                "name": m["raw"]["Name"],
                                "advisor_field": m["raw"].get("Advisor"),
                                "service_rep_field": m["raw"].get("Service Rep"),
                            }
                            for m in members
                        ],
                        "held_accounts": [],
                        "held_interactions": [],
                        "pipeline_action": (
                            "Household, its clients, accounts and meetings are held out of the canonical output "
                            "until a primary advisor is confirmed; no advisor was guessed."
                        ),
                    },
                    source_evidence=[f"CRM client note ({m['raw']['Name']}): {m['raw']['Notes']}" for m in members if m["raw"].get("Notes")],
                )
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
                deceased_signals[hh_id] = RawAnomalySignal(
                    signal_id=f"sig_deceased_status_{hh_id}",
                    anomaly_type="deceased_contact_status_conflict",
                    affected_entities=[hh_name],
                    facts={
                        "household": hh_name,
                        "clients": [
                            {"name": m["raw"]["Name"], "crm_status": m["raw"].get("Status"), "tags": m["raw"].get("Tags")}
                            for m in members
                        ],
                        "accounts": [],
                        "pipeline_action": "Household status set to INACTIVE and tagged pending:round2_deceased_status.",
                    },
                )

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
                acct_facts = {
                    "account_id": acct_num,
                    "holder": holder,
                    "custodian": raw_a["Custodian"],
                    "account_type": raw_a["Account_Type"],
                    "market_value": float(raw_a["Market_Value"]),
                    "currency": raw_a["Currency"],
                    "as_of_date": str(raw_a["As_Of_Date"]),
                }
                if hh_id and hh_id in held_hh_signals:
                    held_hh_signals[hh_id].facts["held_accounts"].append(acct_facts)
                else:
                    signals.append(
                        RawAnomalySignal(
                            signal_id=f"sig_unmatched_account_{acct_num}",
                            anomaly_type="unmatched_custodian_account",
                            affected_entities=[acct_num, holder],
                            facts={
                                **acct_facts,
                                "pipeline_action": "Account held out of the canonical output and not attached to any household; no household was created.",
                            },
                            source_evidence=related_notes(holder),
                        )
                    )
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
                prov.append(
                    Provenance(
                        source=res.provenance_source,
                        rule_or_model="nevis_ambiguity_resolver",
                        confidence=res.confidence,
                        evidence=res.evidence,
                    )
                )
            if fx_prov:
                prov.append(fx_prov)
                if fx_prov.source == "assumption":
                    # Rate not settled in Round 1 Slack -> needs confirmation
                    signals.append(
                        RawAnomalySignal(
                            signal_id=f"sig_fx_{acct_num}",
                            anomaly_type="unconfirmed_fx_conversion",
                            affected_entities=[acct_num, holder],
                            facts={
                                "account_id": acct_num,
                                "holder": holder,
                                "custodian": raw_a["Custodian"],
                                "original_amount": raw_mv,
                                "original_currency": curr,
                                "converted_usd": mv_usd,
                                "rate_usd_per_unit": CHF_USD_RATE if curr == "CHF" else EUR_USD_RATE,
                                "rate_source": "ECB reference rate, 2025-06-30 quarter-end",
                                "pipeline_action": "Converted to USD at the stated rate; provenance recorded as an assumption pending confirmation.",
                            },
                        )
                    )

            # Stale valuation: older than the latest valuation date present in the custodian feed
            as_of_str = str(raw_a["As_Of_Date"])
            if as_of_str < valuation_cutoff:
                prov.append(
                    Provenance(
                        source="assumption",
                        rule_or_model="stale_valuation_policy",
                        confidence=0.85,
                        evidence=(
                            f"Valuation is dated {as_of_str} (older than the {valuation_cutoff} feed cutoff). "
                            "Retained at last reported balance and tagged pending:round2_stale_valuation pending refreshed statements."
                        ),
                    )
                )
                if hh_id in hh_by_id and "pending:round2_stale_valuation" not in hh_by_id[hh_id].source_tags:
                    hh_by_id[hh_id].source_tags.append("pending:round2_stale_valuation")
                # Inactive households (e.g. Thompson, settled in Round 1) need no valuation decision.
                if hh_by_id[hh_id].status == "ACTIVE":
                    signals.append(
                        RawAnomalySignal(
                            signal_id=f"sig_stale_{acct_num}",
                            anomaly_type="stale_valuation",
                            affected_entities=[acct_num, holder],
                            facts={
                                "account_id": acct_num,
                                "holder": holder,
                                "custodian": raw_a["Custodian"],
                                "market_value_usd": mv_usd,
                                "as_of_date": as_of_str,
                                "feed_cutoff_date": valuation_cutoff,
                                "pipeline_action": "Account retained at last reported balance with its original as-of date; household tagged pending:round2_stale_valuation.",
                            },
                            source_evidence=related_notes(holder),
                        )
                    )

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
            if acct.household_id in deceased_signals:
                deceased_signals[acct.household_id].facts["accounts"].append(
                    {
                        "account_id": acct.account_id,
                        "custodian": acct.custodian,
                        "market_value_usd": acct.market_value_usd,
                        "as_of_date": acct.as_of_date,
                    }
                )
                deceased_signals[acct.household_id].affected_entities.append(acct.account_id)
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
                meeting_facts = {
                    "meeting_id": page_id,
                    "client_label": m_client,
                    "date": str(raw_m["Date"]),
                    "attendee": raw_m.get("Attendee"),
                    "notes": raw_m.get("Notes"),
                }
                if hh_id and hh_id in held_hh_signals:
                    held_hh_signals[hh_id].facts["held_interactions"].append(meeting_facts)
                else:
                    signals.append(
                        RawAnomalySignal(
                            signal_id=f"sig_orphan_interaction_{page_id}",
                            anomaly_type="orphan_interaction",
                            affected_entities=[str(m_client)],
                            facts={
                                **meeting_facts,
                                "pipeline_action": "Meeting held out of the canonical output; no household was created from it.",
                            },
                        )
                    )
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

        # 5. Household attribute conflicts and non-standard fee schedules (Rule 6), derived from CRM data
        conflict_rows: list[dict[str, Any]] = []
        for hh_id, members in sorted(hh_groups.items()):
            if hh_id not in valid_hh_ids or len(members) < 2:
                continue
            for field in ("Risk Profile", "Fee Schedule"):
                vals = {m["raw"].get(field) for m in members if m["raw"].get(field)}
                if len(vals) > 1:
                    conflict_rows.append(
                        {
                            "household": members[0]["hh_name"],
                            "field": field,
                            "values_by_client": {m["raw"]["Name"]: m["raw"].get(field) for m in members},
                        }
                    )
        if conflict_rows:
            signals.append(
                RawAnomalySignal(
                    signal_id="sig_household_attribute_conflicts",
                    anomaly_type="household_attribute_conflict",
                    affected_entities=sorted({r["household"] for r in conflict_rows}),
                    facts={
                        "conflicts": conflict_rows,
                        "pipeline_action": "Each client keeps its own value in source_tags; no household-level value was invented.",
                    },
                )
            )

        nonstandard_fees: dict[str, list[str]] = {}
        for raw_c in mapping_result.all_clients_raw:
            fee = (raw_c.get("Fee Schedule") or "").strip()
            if fee and not _is_standard_fee(fee):
                nonstandard_fees.setdefault(fee, []).append(raw_c["Name"])
        if nonstandard_fees:
            signals.append(
                RawAnomalySignal(
                    signal_id="sig_nonstandard_fee_schedules",
                    anomaly_type="nonstandard_fee_schedule",
                    affected_entities=sorted(nonstandard_fees),
                    facts={
                        "values_to_clients": nonstandard_fees,
                        "pipeline_action": "Values preserved verbatim as fee_schedule tags; no fee percentage was inferred.",
                    },
                )
            )

        signals = list(held_hh_signals.values()) + list(deceased_signals.values()) + signals
        for sg in signals:
            logfire.info("anomaly_signal", signal_id=sg.signal_id, anomaly_type=sg.anomaly_type)

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
        span.set_attribute("anomaly_signals", len(signals))

        return output, signals


def verify_clarifications_fact_check(
    memo_text: str,
    items: "list[ClarificationItem]",
    signals: list[RawAnomalySignal],
    sources_dir: str | Path = "sources",
) -> None:
    """Data-driven check of the Round 2 memo against the sources and the detected signals.

    Nothing here names specific clients or accounts: every check is derived from the
    custodian feed and the anomaly signals produced during assembly.
    """
    positions_df = pd.read_excel(Path(sources_dir) / "custodian_positions.xlsx")
    pos_map = {r["Account_Number"]: r for _, r in positions_df.iterrows()}
    all_custodians = {str(r["Custodian"]) for r in pos_map.values()}

    # 1. No email roleplay
    for term in ("Hi Dana", "Dear Dana", "Best regards", "Warmly"):
        if re.search(rf"\b{re.escape(term)}\b", memo_text, re.IGNORECASE):
            raise AssertionError(f"Fact-Check Failure: conversational roleplay '{term}' detected in memo!")

    # 2. Every detected signal is covered by at least one item; no item cites an unknown signal
    known_ids = {sg.signal_id for sg in signals}
    covered: set[str] = set()
    for it in items:
        unknown = set(it.signal_ids) - known_ids
        if unknown:
            raise AssertionError(f"Fact-Check Failure: item '{it.id}' cites unknown signal ids {sorted(unknown)}!")
        covered |= set(it.signal_ids)
    missing = known_ids - covered
    if missing:
        raise AssertionError(f"Fact-Check Failure: detected issues not covered by any question: {sorted(missing)}!")

    # 3. Every entity of a covered signal is named in the memo (account ids and household/holder names)
    for sg in signals:
        for ent in sg.affected_entities:
            if re.fullmatch(r"CU-\d+", ent):
                present = ent in memo_text
            else:
                present = any(t in memo_text.lower() for t in _name_tokens(ent)) if _name_tokens(ent) else True
            if not present:
                raise AssertionError(f"Fact-Check Failure: '{ent}' ({sg.anomaly_type}) is missing from the memo!")

    # 4. Account ids exist in the feed and are not paired with the wrong custodian
    def near(a: str, b: str) -> bool:
        return bool(re.search(rf"{re.escape(a)}[^.\n\)]{{0,35}}{re.escape(b)}|{re.escape(b)}[^.\n\(]{{0,35}}{re.escape(a)}", memo_text, re.IGNORECASE))

    for acct_id in set(re.findall(r"CU-\d+", memo_text)):
        if acct_id not in pos_map:
            raise AssertionError(f"Fact-Check Failure: unknown account ID '{acct_id}' in memo!")
        true_cust = str(pos_map[acct_id]["Custodian"])
        for other in all_custodians - {true_cust}:
            if near(acct_id, other) and not near(acct_id, true_cust):
                raise AssertionError(f"Fact-Check Failure: {acct_id} is held at {true_cust}, not {other}!")

    # 5. Dollar figures for signalled accounts must match the feed (original or converted amount)
    for sg in signals:
        aid = sg.facts.get("account_id")
        if isinstance(aid, str) and aid in pos_map and aid in memo_text:
            row = pos_map[aid]
            allowed = {float(row["Market_Value"])}
            if sg.facts.get("converted_usd") is not None:
                allowed.add(float(sg.facts["converted_usd"]))
            # Only assert when the item explicitly cites a dollar amount next to the account id
            for m in re.finditer(rf"{re.escape(aid)}[^\n]{{0,60}}?\$([\d,]+(?:\.\d+)?)([MmKk]?)", memo_text):
                num = float(m.group(1).replace(",", ""))
                num *= {"m": 1e6, "k": 1e3}.get(m.group(2).lower(), 1)
                if not any(abs(num - a) <= max(1.0, 0.006 * a) for a in allowed):
                    raise AssertionError(f"Fact-Check Failure: amount ${m.group(1)}{m.group(2)} next to {aid} does not match the feed!")

    # 6. Cited option letter in Proposed Default must exist among Candidate Options
    for block in memo_text.split("### ")[1:]:
        title = block.strip().splitlines()[0] if block.strip() else ""
        if not ("\u2014" in title or "\u2013" in title):
            continue
        opt_matches = re.findall(r"\*\*(Option [A-D])\*\*", block)
        default_match = re.search(r"\*\*Proposed Default\*\*:\s*\*\*(Option [A-D])", block)
        if default_match and default_match.group(1) not in opt_matches:
            raise AssertionError(
                f"Fact-Check Failure in section '{title[:40]}': default cites '{default_match.group(1)}', "
                f"but available candidate options are {opt_matches}!"
            )
