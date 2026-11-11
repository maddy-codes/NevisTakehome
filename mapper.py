from pathlib import Path
from typing import Any
import logfire
import pandas as pd
from pydantic import BaseModel, Field

from knowledge import KnowledgeBase
from models import (
    Advisor,
    Provenance,
)


class UnresolvedCase(BaseModel):
    case_id: str
    entity_type: str  # "client" | "account" | "interaction"
    reasons: list[str]
    raw_record: dict[str, Any]
    related_context: dict[str, Any] = Field(default_factory=dict)


class DeterministicMappingResult(BaseModel):
    advisors: list[Advisor]
    all_clients_raw: list[dict[str, Any]]
    all_accounts_raw: list[dict[str, Any]]
    all_interactions_raw: list[dict[str, Any]]
    clean_clients: list[dict[str, Any]]
    clean_accounts: list[dict[str, Any]]
    clean_interactions: list[dict[str, Any]]
    unresolved_cases: list[UnresolvedCase]
    kb_applied_count: int = 0


def parse_notion_folder(folder_path: str | Path) -> pd.DataFrame:
    rows = []
    for md_file in sorted(Path(folder_path).glob("*.md")):
        blocks = md_file.read_text(encoding="utf-8").strip().split("\n\n")
        row: dict[str, Any] = {
            "page_id": md_file.stem.split()[-1],
            "Name": blocks[0].lstrip("# ").strip(),
        }
        for line in blocks[1].splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                row[k.strip()] = v.strip()
        row["Notes"] = "\n\n".join(blocks[2:]).strip() or None
        rows.append(row)
    return pd.DataFrame(rows)


def run_deterministic_mapping(
    sources_dir: str | Path = "sources",
    kb_path: str | Path = "knowledge_base.json",
) -> DeterministicMappingResult:
    sources_path = Path(sources_dir)
    kb = KnowledgeBase.load(kb_path)
    kb_applied_count = 0

    with logfire.span(
        "stage_1.deterministic_mapping",
        sources_dir=str(sources_path),
        existing_kb_rules=len(kb.rules),
    ) as span:
        # 1. Load sources
        with logfire.span("load_raw_sources"):
            roster_df = pd.read_csv(sources_path / "advisor_roster.csv")
            positions_df = pd.read_excel(sources_path / "custodian_positions.xlsx")
            clients_dir = next(
                p for p in (sources_path / "notion_export").iterdir() if p.is_dir() and "Clients" in p.name
            )
            meetings_dir = next(
                p for p in (sources_path / "notion_export").iterdir() if p.is_dir() and "Meetings" in p.name
            )
            clients_df = parse_notion_folder(clients_dir)
            meetings_df = parse_notion_folder(meetings_dir)

        # 2. Map Advisors (100% deterministic from advisor_roster.csv)
        advisors: list[Advisor] = []
        advisor_by_name: dict[str, str] = {}
        for idx, row in roster_df.iterrows():
            adv = Advisor(
                advisor_id=row["advisor_id"],
                full_name=row["full_name"],
                role=row["role"],
                provenance=[
                    Provenance(
                        source="deterministic",
                        rule_or_model="advisor_roster_exact",
                        confidence=1.0,
                        evidence=f"advisor_roster.csv row {idx}",
                    )
                ],
            )
            advisors.append(adv)
            advisor_by_name[row["full_name"]] = row["advisor_id"]

        clients_records = [
            {k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in clients_df.to_dict(orient="records")
        ]
        positions_records = [
            {k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in positions_df.to_dict(orient="records")
        ]
        meetings_records = [
            {k: (None if pd.isna(v) else v) for k, v in r.items()}
            for r in meetings_df.to_dict(orient="records")
        ]

        exact_client_by_name = {r["Name"]: r for r in clients_records}

        STRICT_STATUS_MAP = {
            "Active": "ACTIVE",
            "ACTIVE": "ACTIVE",
            "active": "ACTIVE",
            "Inactive": "INACTIVE",
            "Prospect": "PROSPECT",
        }
        STRICT_ACCT_TYPE_MAP = {
            "Individual": "INDIVIDUAL",
            "Joint WROS": "JOINT",
            "Joint TIC": "JOINT",
            "Trust-Rev": "TRUST",
            "IRA": "IRA",
            "Rollover IRA": "IRA",
            "Roth IRA": "ROTH_IRA",
            "Corporate": "CORPORATE",
        }
        STRICT_INTERACTION_MAP = {
            "Review": "REVIEW",
            "Annual Review": "REVIEW",
            "QBR": "REVIEW",
            "Check-in": "REVIEW",
            "Prospecting": "PROSPECTING",
            "Intro Call": "PROSPECTING",
            "Discovery": "PROSPECTING",
            "Onboarding": "ONBOARDING",
        }

        clean_clients: list[dict[str, Any]] = []
        clean_accounts: list[dict[str, Any]] = []
        clean_interactions: list[dict[str, Any]] = []
        unresolved_cases: list[UnresolvedCase] = []

        # 3. Pass 1: Clients — check deterministic rules + KnowledgeBase before marking unresolved
        with logfire.span("pass_1.clients"):
            for r in clients_records:
                r_work = dict(r)
                r_work["_kb_provenance"] = []
                r_work["_kb_extra_tags"] = []

                # Check if known duplicate in KB
                dup_rule = kb.get_rule("duplicate_client", r_work["Name"])
                if dup_rule:
                    kb_applied_count += 1
                    continue

                raw_status = (r_work.get("Status") or "").strip()
                status_rule = kb.get_rule("status_map", raw_status)
                if status_rule and status_rule.target_value:
                    r_work["_resolved_status"] = status_rule.target_value
                    r_work["_kb_extra_tags"].extend(status_rule.extra_tags)
                    r_work["_kb_provenance"].append(status_rule.model_dump())
                    kb_applied_count += 1

                adv_val = r_work.get("Advisor")
                adv_rule = kb.get_rule("advisor_alias", adv_val)
                if adv_rule and adv_rule.target_value:
                    r_work["_resolved_advisor_id"] = adv_rule.target_value
                    r_work["_kb_provenance"].append(adv_rule.model_dump())
                    kb_applied_count += 1

                hh_rule = kb.get_rule("household_link", r_work["Name"])
                if hh_rule and hh_rule.target_value:
                    r_work["Household"] = hh_rule.target_value
                    r_work["_kb_provenance"].append(hh_rule.model_dump())
                    kb_applied_count += 1

                reasons = []
                if raw_status not in STRICT_STATUS_MAP and "_resolved_status" not in r_work:
                    reasons.append(f"non_standard_status:{raw_status}")
                if not adv_val and "_resolved_advisor_id" not in r_work:
                    reasons.append("missing_advisor")
                elif adv_val and adv_val not in advisor_by_name and "_resolved_advisor_id" not in r_work:
                    reasons.append(f"unmatched_advisor:{adv_val}")
                if not r_work.get("Household"):
                    reasons.append("missing_household")
                if r_work.get("Notes") and not r_work["_kb_provenance"]:
                    reasons.append("has_unstructured_note")
                rep_val = r_work.get("Service Rep")
                if rep_val and not kb.get_rule("ignored_field", "Service Rep"):
                    reasons.append(f"has_service_rep:{rep_val}")
                tag_val = r_work.get("Tags")
                if tag_val in ("Deceased", "Held Away"):
                    reasons.append(f"critical_tag:{tag_val}")
                if "," in r_work["Name"] and not dup_rule:
                    reasons.append("inverted_or_duplicate_name_format")

                if reasons:
                    page_id = r_work["page_id"][:8]
                    unresolved_cases.append(
                        UnresolvedCase(
                            case_id=f"client:{page_id}",
                            entity_type="client",
                            reasons=reasons,
                            raw_record=r_work,
                        )
                    )
                else:
                    clean_clients.append(r_work)

        # 4. Pass 2: Accounts — check deterministic rules + KnowledgeBase
        with logfire.span("pass_2.accounts"):
            for r in positions_records:
                r_work = dict(r)
                r_work["_kb_provenance"] = []
                holder = r_work["Account_Holder"]
                curr = r_work["Currency"]
                as_of = str(r_work["As_Of_Date"])
                acct_type = r_work["Account_Type"]
                acct_num = r_work["Account_Number"]

                holder_rule = kb.get_rule("account_holder_to_household", holder)
                if holder_rule and holder_rule.target_value:
                    r_work["_resolved_household"] = holder_rule.target_value
                    r_work["_kb_provenance"].append(holder_rule.model_dump())
                    kb_applied_count += 1

                fx_rule = kb.get_rule("fx_rate", curr)
                if curr != "USD" and fx_rule and fx_rule.target_value:
                    import re as _re
                    m_num = _re.search(r"[0-9]+(?:\.[0-9]+)?", fx_rule.target_value)
                    if m_num:
                        r_work["_resolved_market_value_usd"] = round(
                            float(r_work["Market_Value"]) * float(m_num.group(0)), 2
                        )
                        r_work["_kb_provenance"].append(fx_rule.model_dump())
                        kb_applied_count += 1

                reasons = []
                if holder not in exact_client_by_name and "_resolved_household" not in r_work:
                    reasons.append(f"unmatched_account_holder:{holder}")
                if curr != "USD" and "_resolved_market_value_usd" not in r_work:
                    reasons.append(f"non_usd_currency:{curr}")
                if as_of != "2025-06-30":
                    reasons.append(f"stale_as_of_date:{as_of}")
                if acct_type not in STRICT_ACCT_TYPE_MAP:
                    reasons.append(f"unmapped_account_type:{acct_type}")

                if reasons:
                    unresolved_cases.append(
                        UnresolvedCase(
                            case_id=f"account:{acct_num}",
                            entity_type="account",
                            reasons=reasons,
                            raw_record=r_work,
                        )
                    )
                else:
                    clean_accounts.append(r_work)

        # 5. Pass 3: Interactions (Meetings) — check deterministic rules + KnowledgeBase
        with logfire.span("pass_3.interactions"):
            for r in meetings_records:
                r_work = dict(r)
                r_work["_kb_provenance"] = []
                client_name = r_work.get("Client")
                attendee = r_work.get("Attendee")
                m_type = r_work.get("Type")
                page_id = r_work["page_id"][:8]

                m_cli_rule = kb.get_rule("meeting_client_alias", client_name)
                if m_cli_rule and m_cli_rule.target_value:
                    r_work["Client"] = m_cli_rule.target_value
                    client_name = r_work["Client"]
                    r_work["_kb_provenance"].append(m_cli_rule.model_dump())
                    kb_applied_count += 1

                att_rule = kb.get_rule("advisor_alias", attendee)
                dep_rule = kb.get_rule("departed_staff", attendee)
                if att_rule and att_rule.target_value:
                    r_work["_resolved_advisor_id"] = att_rule.target_value
                    r_work["_kb_provenance"].append(att_rule.model_dump())
                    kb_applied_count += 1
                elif dep_rule:
                    r_work["Attendee"] = None
                    attendee = None
                    r_work["_kb_provenance"].append(dep_rule.model_dump())
                    kb_applied_count += 1

                reasons = []
                if client_name not in exact_client_by_name:
                    reasons.append(f"unmatched_meeting_client:{client_name}")
                if not attendee and "_resolved_advisor_id" not in r_work and not dep_rule:
                    reasons.append("missing_attendee")
                elif attendee and attendee not in advisor_by_name and "_resolved_advisor_id" not in r_work:
                    reasons.append(f"unmatched_attendee:{attendee}")
                if r_work.get("Notes") and not r_work["_kb_provenance"]:
                    reasons.append("has_meeting_note")
                if m_type not in STRICT_INTERACTION_MAP:
                    reasons.append(f"unmapped_interaction_type:{m_type}")

                if reasons:
                    unresolved_cases.append(
                        UnresolvedCase(
                            case_id=f"interaction:{page_id}",
                            entity_type="interaction",
                            reasons=reasons,
                            raw_record=r_work,
                        )
                    )
                else:
                    clean_interactions.append(r_work)

        span.set_attribute("clean_clients_count", len(clean_clients))
        span.set_attribute("clean_accounts_count", len(clean_accounts))
        span.set_attribute("clean_interactions_count", len(clean_interactions))
        span.set_attribute("unresolved_cases_count", len(unresolved_cases))
        span.set_attribute("kb_applied_count", kb_applied_count)

        logfire.info(
            "Stage 1 deterministic mapping complete",
            clean_clients=len(clean_clients),
            clean_accounts=len(clean_accounts),
            clean_interactions=len(clean_interactions),
            unresolved_cases=len(unresolved_cases),
            kb_applied_count=kb_applied_count,
        )

        return DeterministicMappingResult(
            advisors=advisors,
            all_clients_raw=clients_records,
            all_accounts_raw=positions_records,
            all_interactions_raw=meetings_records,
            clean_clients=clean_clients,
            clean_accounts=clean_accounts,
            clean_interactions=clean_interactions,
            unresolved_cases=unresolved_cases,
            kb_applied_count=kb_applied_count,
        )
