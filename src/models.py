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


class ClarificationItem(BaseModel):
    id: str
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

