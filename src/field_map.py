"""Field dispositions: an explicit decision for every column in every source (canonical Rule 6).

Each source column is mapped, normalized, preserved as a source tag, read by the agent, kept as an internal
key, or dropped with a stated reason. A column that is not listed here stops the run, so a new field in a
future sync is surfaced for a decision instead of being silently ignored.
"""

from pathlib import Path
from typing import Iterable, Literal

Disposition = Literal["map", "normalize", "preserve", "agent", "internal", "drop"]

# source -> column -> (disposition, destination, rationale)
FIELD_MAP: dict[str, dict[str, tuple[Disposition, str, str]]] = {
    "advisor_roster.csv": {
        "advisor_id": ("map", "advisor.advisor_id", ""),
        "full_name": ("map", "advisor.full_name", ""),
        "role": ("map", "advisor.role", ""),
        "office": ("preserve", "advisor.source_tags (office:<city>)", "No column in the canonical advisor; location is business-meaningful, so it is kept as an annotation, not dropped."),
    },
    "Notion clients": {
        "page_id": ("internal", "client_id key", ""),
        "Name": ("normalize", "client.first_name / last_name", "Inverted 'Last, First' exports are split."),
        "Status": ("normalize", "household.status", "Free-text enum; Legacy -> ACTIVE + lineage tag (Slack)."),
        "Advisor": ("map", "household.primary_advisor_id", "Abbreviations resolved; blank is a blocker (Slack: don't guess)."),
        "Service Rep": ("preserve", "client.source_tags (service_rep:<name>)", "Never the advisor (Slack); kept as paperwork ownership."),
        "Household": ("normalize", "household.household_id / household_name", "Blank is linked from notes/context by the agent."),
        "Segment": ("preserve", "source_tags (segment:)", ""),
        "Client Since": ("preserve", "source_tags (client_since:ISO date)", ""),
        "Risk Profile": ("preserve", "source_tags (risk_profile:)", "Per person; differences inside a household are not a contradiction."),
        "Fee Schedule": ("preserve", "source_tags (fee_schedule:)", "Kept verbatim, no percentage inferred."),
        "Referred By": ("preserve", "source_tags (referred_by:)", ""),
        "Tags": ("preserve", "source_tags (tag:)", "Deceased is also a flag trigger (contradiction with Active status)."),
        "Website": ("drop", "-", "Synthetic URL with no onboarding value."),
        "Notes": ("agent", "tags / role / status / blocker", "Page-body notes are read by the agent; facts that matter become tags, roles or blockers. No free-text column exists in the model."),
    },
    "Notion meetings": {
        "page_id": ("internal", "interaction_id key", ""),
        "Name": ("drop", "-", "Page title; redundant with Client + Type + Date."),
        "Client": ("map", "interaction.household_id", "Person name resolved to a household; unmatched is a blocker."),
        "Type": ("normalize", "interaction.interaction_type", ""),
        "Date": ("normalize", "interaction.interaction_date", "Prose dates to ISO."),
        "Attendee": ("map", "interaction.advisor_id", "Nullable; departed staff are not accepted as advisors."),
        "Notes": ("map", "interaction.summary", ""),
    },
    "custodian_positions.xlsx": {
        "Account_Number": ("map", "account.account_id", ""),
        "Account_Holder": ("map", "account.household_id", "Holder string resolved to a household; unmatched is a blocker."),
        "Account_Type": ("normalize", "account.account_type", ""),
        "Market_Value": ("normalize", "account.market_value_usd", "Converted to USD at quarter-end FX when not USD."),
        "Cost_Basis": ("drop", "-", "Tax-only; Dana: ignore, AUM is market value (Slack)."),
        "Currency": ("map", "account.currency_original", ""),
        "As_Of_Date": ("map", "account.as_of_date", "Older than the latest feed date is a stale-valuation blocker for active households."),
        "Custodian": ("map", "account.custodian", ""),
    },
}


def check_columns(source: str, columns: Iterable[str]) -> None:
    """Fail loudly if a source column has no recorded disposition (Rule 6: never silently drop)."""
    unknown = [c for c in columns if c not in FIELD_MAP[source]]
    if unknown:
        raise ValueError(
            f"Unacknowledged column(s) {unknown} in {source}. Decide map / preserve / drop / flag and add them to src/field_map.py."
        )


def render_markdown() -> str:
    lines = ["# Field Dispositions", "", "Every source column and where it goes (canonical Rule 6). Generated from `src/field_map.py`.", ""]
    for source, cols in FIELD_MAP.items():
        lines += [f"## {source}", "", "| Column | Disposition | Destination | Why |", "|---|---|---|---|"]
        for col, (disp, dest, why) in cols.items():
            lines.append(f"| `{col}` | {disp} | {dest} | {why} |")
        lines.append("")
    return "\n".join(lines)


def write_markdown(path: str | Path = "outputs/field_dispositions.md") -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(render_markdown(), encoding="utf-8")
