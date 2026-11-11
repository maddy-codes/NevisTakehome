"""Blocker ledger: the document the resolver agent writes its flagged items into.

Stage 2 decides (per record) what is a blocker; this module persists those decisions as
`outputs/blockers.json` (machine) and `outputs/blockers.md` (human audit trail). The Round 2
memo is then marked out of the ledger, never from separate detection logic.
"""

import json
import re
from pathlib import Path

import pandas as pd

from src.models import Blocker, ClarificationItem, Holdout
from src.resolver import CaseResolution

_STOPWORDS = {"llc", "inc", "trust", "revocable", "household", "holdings", "the", "and", "joint", "account"}


def name_tokens(text: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z]{3,}", (text or "").lower()) if t not in _STOPWORDS}


def collect_blockers(resolutions: list[CaseResolution]) -> list[Blocker]:
    blockers: list[Blocker] = []
    for res in resolutions:
        if res.action == "flag_for_clarification" and res.blocker is not None:
            blockers.append(
                res.blocker.model_copy(update={"blocker_id": f"blk_{res.case_id.replace(':', '_')}", "case_id": res.case_id})
            )
    return blockers


def group_blockers(blockers: list[Blocker]) -> list[list[Blocker]]:
    """One decision per group: blockers of the same flag rule, plus any that share an affected entity."""
    parent = list(range(len(blockers)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        parent[find(i)] = find(j)

    seen: dict[str, int] = {}
    for i, b in enumerate(blockers):
        for key in [f"rule:{b.matrix_rule}", *[f"ent:{e.lower()}" for e in b.affected_entities if re.fullmatch(r"CU-\d+", e)]]:
            if key in seen:
                union(i, seen[key])
            else:
                seen[key] = i
    groups: dict[int, list[Blocker]] = {}
    for i, b in enumerate(blockers):
        groups.setdefault(find(i), []).append(b)
    return list(groups.values())


def attach_account_facts(blockers: list[Blocker], sources_dir: str | Path) -> list[Blocker]:
    """Ground each blocker with the custodian-feed facts of every account it names (facts only)."""
    df = pd.read_excel(Path(sources_dir) / "custodian_positions.xlsx")
    feed = {str(r["Account_Number"]): r for _, r in df.iterrows()}
    out: list[Blocker] = []
    for b in blockers:
        ids = sorted({e for e in b.affected_entities if re.fullmatch(r"CU-\d+", e)} | set(re.findall(r"CU-\d+", b.case_id)))
        facts = [
            {
                "account_id": i,
                "holder": str(feed[i]["Account_Holder"]),
                "custodian": str(feed[i]["Custodian"]),
                "market_value": float(feed[i]["Market_Value"]),
                "currency": str(feed[i]["Currency"]),
                "as_of_date": str(feed[i]["As_Of_Date"]),
            }
            for i in ids
            if i in feed
        ]
        out.append(b.model_copy(update={"account_facts": facts}))
    return out


def write_blocker_ledger(
    resolutions: list[CaseResolution],
    json_path: str | Path = "outputs/blockers.json",
    md_path: str | Path = "outputs/blockers.md",
    sources_dir: str | Path = "sources",
) -> list[Blocker]:
    blockers = attach_account_facts(collect_blockers(resolutions), sources_dir)
    applied = [r for r in resolutions if r.action != "flag_for_clarification"]

    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps([b.model_dump() for b in blockers], indent=2), encoding="utf-8")

    lines = [
        "# Blocker Ledger",
        "",
        f"Written by the resolver agent. {len(blockers)} blocker(s) flagged, {len(applied)} case(s) decided without flagging.",
        "Matrix rules are defined in `src/flag_matrix.py`.",
        "",
        "## Blockers (flagged)",
        "",
    ]
    for b in blockers:
        lines += [
            f"### {b.blocker_id} — {b.category}  (rule {b.matrix_rule}, case `{b.case_id}`)",
            f"- **Affected**: {', '.join(b.affected_entities)}",
            *[
                f"- **Account {f['account_id']}**: {f['holder']}, {f['custodian']}, {f['market_value']:,.0f} {f['currency']}, as of {f['as_of_date']}"
                for f in b.account_facts
            ],
            f"- **Trigger**: {b.trigger}",
            f"- **Evidence**: {b.evidence}",
            "- **Options**:",
            *[f"  - {o}" for o in b.candidate_options],
            f"- **Proposed default**: {b.proposed_default}",
            f"- **Question**: {b.question_for_dana}",
            "",
        ]
    lines += ["## Decided without flagging", ""]
    for r in applied:
        lines.append(f"- `{r.case_id}` — {r.action} (confidence {r.confidence:.2f}, {r.provenance_source}): {r.evidence}")
    lines.append("")
    Path(md_path).write_text("\n".join(lines), encoding="utf-8")
    return blockers


def check_holdouts_covered(holdouts: list[Holdout], blockers: list[Blocker]) -> None:
    """Post-mapping validation: nothing may be held out of the canonical output without a blocker explaining it."""
    haystacks = [
        (b.blocker_id, (" ".join(b.affected_entities + [b.trigger, b.evidence, b.question_for_dana])).lower())
        for b in blockers
    ]
    uncovered: list[Holdout] = []
    for h in holdouts:
        keys = {h.entity_id.lower()} if re.fullmatch(r"CU-\d+", h.entity_id) else set()
        toks = name_tokens(h.label) or name_tokens(h.entity_id)
        hit = False
        for _, hay in haystacks:
            if any(k in hay for k in keys) or (toks and toks <= name_tokens(hay)):
                hit = True
                break
        if not hit:
            uncovered.append(h)
    if uncovered:
        detail = "; ".join(f"{h.kind} {h.entity_id} ({h.label}): {h.reason}" for h in uncovered)
        raise AssertionError(
            f"Validation Failure: {len(uncovered)} record(s) held out of canonical output without a blocker: {detail}"
        )


def verify_memo_against_ledger(
    memo_text: str,
    items: list[ClarificationItem],
    blockers: list[Blocker],
    sources_dir: str | Path = "sources",
) -> None:
    groups = group_blockers(blockers)
    if len(items) != len(groups):
        raise AssertionError(f"Fact-Check Failure: expected {len(groups)} decision items (one per group), got {len(items)}!")
    by_id = {b.blocker_id: b for b in blockers}
    action_words = {
        "hold_out": r"\b(hold|held|exclud\w*|outside|out of|unassigned|not (?:be )?(?:assign|attach|creat|load|import)\w*)\b",
        "set_inactive": r"\binactive\b",
        "retain_and_tag": r"\b(retain\w*|keep|kept|tag\w*)\b",
    }
    for grp in groups:
        ids = {b.blocker_id for b in grp}
        covering = [it for it in items if ids <= set(it.blocker_ids)]
        if not covering:
            raise AssertionError(f"Fact-Check Failure: blockers {sorted(ids)} must be covered together in a single item!")
        # The memo's proposed default must agree with the default the assembler actually applied
        for act in {by_id[i].default_action for i in ids}:
            if not re.search(action_words[act], covering[0].proposed_default, re.IGNORECASE):
                raise AssertionError(
                    f"Fact-Check Failure: item '{covering[0].id}' default does not reflect the applied action '{act}' "
                    f"({'; '.join(by_id[i].proposed_default for i in sorted(ids))})!"
                )
    """Data-driven check of the Round 2 memo against the custodian feed and the blocker ledger."""
    positions_df = pd.read_excel(Path(sources_dir) / "custodian_positions.xlsx")
    pos_map = {str(r["Account_Number"]): r for _, r in positions_df.iterrows()}
    all_custodians = {str(r["Custodian"]) for r in pos_map.values()}

    for term in ("Hi Dana", "Dear Dana", "Best regards", "Warmly"):
        if re.search(rf"\b{re.escape(term)}\b", memo_text, re.IGNORECASE):
            raise AssertionError(f"Fact-Check Failure: conversational roleplay '{term}' detected in memo!")

    # Every blocker is covered exactly by the memo; no item cites an unknown blocker
    known = {b.blocker_id for b in blockers}
    covered: set[str] = set()
    for it in items:
        unknown = set(it.blocker_ids) - known
        if unknown:
            raise AssertionError(f"Fact-Check Failure: item '{it.id}' cites unknown blockers {sorted(unknown)}!")
        covered |= set(it.blocker_ids)
    if known - covered:
        raise AssertionError(f"Fact-Check Failure: blockers not covered by any question: {sorted(known - covered)}!")

    # Entities of each blocker appear in the memo
    for b in blockers:
        for ent in b.affected_entities:
            if re.fullmatch(r"CU-\d+", ent):
                present = ent in memo_text
            else:
                toks = name_tokens(ent)
                present = any(t in memo_text.lower() for t in toks) if toks else True
            if not present:
                raise AssertionError(f"Fact-Check Failure: '{ent}' ({b.blocker_id}) is missing from the memo!")

    # Every account a blocker names is stated with its true custodian (Dana must be able to find it)
    for b in blockers:
        for f in b.account_facts:
            if not re.search(
                rf"{re.escape(f['account_id'])}[^.\n]{{0,60}}{re.escape(f['custodian'])}|{re.escape(f['custodian'])}[^.\n]{{0,60}}{re.escape(f['account_id'])}",
                memo_text,
                re.IGNORECASE,
            ):
                raise AssertionError(f"Fact-Check Failure: {f['account_id']} must be stated with its custodian {f['custodian']} and amount!")

    # Account ids exist and are not paired with the wrong custodian
    def near(a: str, c: str) -> bool:
        return bool(
            re.search(rf"{re.escape(a)}[^.\n\)]{{0,35}}{re.escape(c)}|{re.escape(c)}[^.\n\(]{{0,35}}{re.escape(a)}", memo_text, re.IGNORECASE)
        )

    for acct_id in set(re.findall(r"CU-\d+", memo_text)):
        if acct_id not in pos_map:
            raise AssertionError(f"Fact-Check Failure: unknown account ID '{acct_id}' in memo!")
        true_cust = str(pos_map[acct_id]["Custodian"])
        for other in all_custodians - {true_cust}:
            if near(acct_id, other) and not near(acct_id, true_cust):
                raise AssertionError(f"Fact-Check Failure: {acct_id} is held at {true_cust}, not {other}!")

        # A dollar amount written right after the id must match the feed (original, or converted at the stated rate)
        mv = float(pos_map[acct_id]["Market_Value"])
        for m in re.finditer(rf"{re.escape(acct_id)}[^\n$]{{0,60}}\$([\d,]+(?:\.\d+)?)([MmKk]?)", memo_text):
            num = float(m.group(1).replace(",", "")) * {"m": 1e6, "k": 1e3}.get(m.group(2).lower(), 1)
            if str(pos_map[acct_id]["Currency"]) == "USD" and abs(num - mv) > max(1.0, 0.006 * mv):
                raise AssertionError(f"Fact-Check Failure: ${m.group(1)}{m.group(2)} next to {acct_id} does not match the feed (${mv:,.0f})!")

    # Cited option letter in Proposed Default must exist among Candidate Options
    for block in memo_text.split("### ")[1:]:
        title = block.strip().splitlines()[0] if block.strip() else ""
        if "—" not in title and "–" not in title:
            continue
        opts = re.findall(r"\*\*(Option [A-D])\*\*", block)
        default = re.search(r"\*\*Proposed Default\*\*:\s*\*\*(Option [A-D])", block)
        if default and default.group(1) not in opts:
            raise AssertionError(
                f"Fact-Check Failure in '{title[:40]}': default cites '{default.group(1)}' but options are {opts}!"
            )
