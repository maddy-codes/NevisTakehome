from typing import Any, Literal
from pydantic import BaseModel, Field

HouseholdStatus = Literal["ACTIVE", "INACTIVE", "PROSPECT"]
ClientRole = Literal["PRIMARY", "SPOUSE", "DEPENDENT", "SIGNER", "OTHER"]
AccountType = Literal["INDIVIDUAL", "JOINT", "TRUST", "IRA", "ROTH_IRA", "CORPORATE", "OTHER"]
InteractionType = Literal["REVIEW", "PROSPECTING", "ONBOARDING", "OTHER"]
ProvenanceSource = Literal["deterministic", "slack_knowledge", "llm", "assumption", "human"]


class Provenance(BaseModel):
    source: ProvenanceSource
    rule_or_model: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: str


class Advisor(BaseModel):
    advisor_id: str
    full_name: str
    role: str
    provenance: list[Provenance] = Field(default_factory=list)


class Household(BaseModel):
    household_id: str
    household_name: str
    primary_advisor_id: str
    status: HouseholdStatus
    as_of_date: str | None = None
    aum_usd: float | None = None
    source_tags: list[str] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)


class Client(BaseModel):
    client_id: str
    household_id: str
    first_name: str
    last_name: str
    role: ClientRole
    source_tags: list[str] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)


class Account(BaseModel):
    account_id: str
    household_id: str
    account_type: AccountType
    market_value_usd: float | None = None
    currency_original: str
    as_of_date: str
    custodian: str
    provenance: list[Provenance] = Field(default_factory=list)


class Interaction(BaseModel):
    interaction_id: str
    household_id: str
    interaction_type: InteractionType
    interaction_date: str
    advisor_id: str | None = None
    summary: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class RawAnomalySignal(BaseModel):
    signal_id: str
    anomaly_type: str
    affected_entities: list[str]
    facts: dict[str, Any]
    source_evidence: list[str] = Field(default_factory=list)


FlagRule = Literal["F1", "F2", "F3", "F4", "F5", "F6", "F7"]


class Blocker(BaseModel):
    """A record the agent decided it cannot resolve confidently. Written to the blocker ledger."""

    blocker_id: str = ""  # assigned when written to the ledger
    case_id: str = ""  # assigned when written to the ledger
    matrix_rule: FlagRule = Field(description="Flag-matrix rule id F1-F7 that justifies flagging this record.")
    category: str = Field(description="Short label, e.g. 'Missing primary advisor'.")
    trigger: str = Field(description="What triggered the flag, in one or two sentences.")
    evidence: str = Field(description="Exact evidence: verbatim note quotes, Slack guidance, source values.")
    candidate_options: list[str] = Field(description="2-3 options labelled 'Option A', 'Option B', 'Option C'.")
    proposed_default: str = Field(description="The conservative default; must cite one option letter.")
    # Mechanical effect of proposed_default, applied by the assembler so output and memo cannot disagree:
    #   hold_out: keep the record out of canonical output; retain_and_tag: keep it with original values, tagged pending;
    #   set_inactive: household status INACTIVE, tagged pending.
    default_action: Literal["hold_out", "retain_and_tag", "set_inactive"] = Field(
        description="Mechanical effect of proposed_default: hold_out, retain_and_tag or set_inactive."
    )
    question_for_dana: str = Field(description="REQUIRED. The single scoped question Dana can answer in one line.")
    affected_entities: list[str] = Field(default_factory=list)  # account ids, client/household names, meeting names
    # Filled from the custodian feed when the ledger is written (facts only, never written by the LLM)
    account_facts: list[dict] = Field(default_factory=list)


class Holdout(BaseModel):
    """A record the assembler kept out of canonical output (facts only, no recommendation)."""

    kind: Literal["household", "account", "interaction"]
    entity_id: str
    label: str
    reason: str


class ClarificationItem(BaseModel):
    id: str
    blocker_ids: list[str] = Field(default_factory=list)
    category: str
    trigger: str
    evidence: str
    candidate_options: list[str]
    proposed_default: str
    question_for_dana: str


class CanonicalOutput(BaseModel):
    advisors: list[Advisor] = Field(default_factory=list)
    households: list[Household] = Field(default_factory=list)
    clients: list[Client] = Field(default_factory=list)
    accounts: list[Account] = Field(default_factory=list)
    interactions: list[Interaction] = Field(default_factory=list)

