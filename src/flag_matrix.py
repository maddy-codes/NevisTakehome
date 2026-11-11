"""The flag / don't-flag matrix that routes each ambiguous record to the clean output or to a blocker.

Derived from the Nevis canonical rules (reference PDF) and the Round 1 Slack thread. It is rendered into
the agent prompts so the LLM makes the call; it is not applied as code against specific clients.
"""

FLAG_MATRIX = """\
### Flag matrix — decide per record: `auto_apply`, `drop_duplicate`, or `flag_for_clarification`

FLAG (action = flag_for_clarification, attach a `blocker`, set `matrix_rule`):
| id | Flag when | Source of the rule |
|----|-----------|--------------------|
| F1 | The primary advisor cannot be determined: Advisor field blank, only a Service Rep present, or the named person is departed per Slack. Never guess or fall back to the Service Rep. | Canonical rule 1 + Slack ("Don't guess. Flag those to me"; departed contractor) |
| F2 | A custodian account holder cannot be matched to exactly one CRM client/household with confidence. | Canonical rule 4 (no orphan accounts) |
| F3 | A meeting's client cannot be matched to an existing household (never mint a household from a meeting). | Canonical rule 7 (no orphan interactions) |
| F4 | Two sources genuinely contradict each other about the same entity and no Slack answer settles it (e.g. an Active status vs a tag/note saying the contact is deceased). Propose a conservative default. | Canonical rule 6 (flag genuine contradictions) |
| F5 | An account in an ACTIVE household has a valuation older than the most recent quarter-end present in the custodian feed, and Slack did not address stale valuations. | Slack ("market value as of the most recent quarter-end") |
| F6 | After reading notes and cross-source context, the entity link is still ambiguous (confidence < 0.80 or more than one plausible target). | Task brief (confidence routing) |
| F7 | A page note states an open question or a pending decision for operations (e.g. "not sure whether…", "flag for ops", "family still deciding"). | Task brief (page bodies matter) |

DO NOT FLAG (action = auto_apply or drop_duplicate; record provenance; never create a blocker):
| id | Situation | Why |
|----|-----------|-----|
| D1 | Status "Legacy" -> ACTIVE with tag `lineage:harborline`. | Slack |
| D2 | Service Rep present: it is never the advisor, preserve as a `service_rep:` tag. (Flagging only happens under F1 when the Advisor is missing.) | Slack |
| D3 | Cost Basis column. | Slack (ignore; tax only) |
| D4 | Any non-USD balance: it is converted to USD by the assembler at quarter-end FX with a provenance note. Never flag currency. | Slack + canonical rule 5 |
| D5 | A duplicate client record that Slack already confirmed (collapse it). | Slack |
| D6 | Former / Churned / Thompson-style departed households -> INACTIVE, excluded from active AUM; do not ask again. | Slack |
| D7 | Enum or format normalization, inverted names, abbreviations, nicknames, trust/joint holder names that you can resolve at confidence >= 0.80 from the CRM and notes (use provenance_source "llm"). | Task brief |
| D8 | Co-members of a household with different Risk Profile / Fee Schedule values, and non-percentage fee labels (Tier 1, See LOE, negotiated). Preserve each verbatim in source_tags. These are attributes of different people, not a contradiction; do not dump them into flags. | Canonical rule 6 ("dumping everything into flags is wrong") |
| D9 | Fields with no business meaning (Website, office). Drop with a one-line rationale. | Canonical rule 6 |
| D10 | Anything already covered by an existing KnowledgeBase rule whose provenance is `slack_knowledge` or `human`. Rules with provenance `assumption` or `llm` are unconfirmed defaults: they do NOT settle a question that a FLAG row (F1-F7) still applies to. | Knowledge layer |

If a record matches both a FLAG and a DO NOT FLAG row, the DO NOT FLAG row wins only when Slack explicitly settled it;
otherwise flag. Flag only what a person must decide; every blocker must be a scoped, answerable question.
"""
