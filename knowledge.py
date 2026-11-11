from pathlib import Path
from typing import Literal
import logfire
from pydantic import BaseModel, Field

from models import ProvenanceSource


RuleType = Literal[
    "status_map",
    "advisor_alias",
    "departed_staff",
    "duplicate_client",
    "household_link",
    "account_holder_to_household",
    "meeting_client_alias",
    "fx_rate",
    "ignored_field",
]


class KnowledgeRule(BaseModel):
    rule_id: str = Field(description="Deterministic key formatted as '<rule_type>:<source_value>'")
    rule_type: RuleType
    scope: Literal["firm_specific", "global_reusable"] = "firm_specific"
    source_value: str
    target_value: str | None = None
    extra_tags: list[str] = Field(default_factory=list)
    provenance_source: ProvenanceSource = "slack_knowledge"
    evidence: str
    version: int = 1
    active: bool = True


class KnowledgeBase(BaseModel):
    rules: dict[str, KnowledgeRule] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path = "knowledge_base.json") -> "KnowledgeBase":
        p = Path(path)
        if p.exists():
            return cls.model_validate_json(p.read_text(encoding="utf-8"))
        return cls()

    def save(self, path: str | Path = "knowledge_base.json") -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")

    def upsert(self, rule: KnowledgeRule) -> None:
        canonical_key = f"{rule.rule_type}:{rule.source_value}"
        rule.rule_id = canonical_key
        existing = self.rules.get(canonical_key)
        if existing:
            if existing.target_value != rule.target_value or existing.extra_tags != rule.extra_tags:
                rule.version = existing.version + 1
                logfire.info(
                    "Updated existing knowledge rule",
                    rule_id=canonical_key,
                    old_target=existing.target_value,
                    new_target=rule.target_value,
                    version=rule.version,
                )
            else:
                rule.version = existing.version
        self.rules[canonical_key] = rule

    def get_rule(self, rule_type: RuleType, source_value: str | None) -> KnowledgeRule | None:
        if not source_value:
            return None
        r = self.rules.get(f"{rule_type}:{source_value}")
        return r if (r and r.active) else None

