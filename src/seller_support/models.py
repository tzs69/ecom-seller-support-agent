"""Domain records and the smaller model-facing assessment schema."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Decision = Literal[
    "needs_order_id",
    "order_unavailable",
    "unsupported_policy_scope",
    "outside_workflow",
    "insufficient_evidence",
    "existing_resolution",
    "human_review",
    "propose_carrier_investigation",
]
Action = Literal["submit_carrier_investigation_request"]
SourceType = Literal["business_policy", "backend_control", "agent_instruction"]

INACCESSIBLE_MESSAGE = (
    "I couldn't access that order for your seller account. Please check the order ID."
)


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseInput(Record):
    case_id: str
    order_id: str | None
    seller_message: str
    authenticated_seller_id: str
    evaluation_time: datetime
    tool_overrides: dict = Field(default_factory=dict)


class Order(Record):
    order_id: str
    seller_id: str
    market: str
    currency: str
    total_cents: int = Field(gt=0)
    status: str
    destination_token: str
    tracking_id: str


class Tracking(Record):
    tracking_id: str
    status: str
    delivered_at: datetime | None
    delivery_location_token: str | None
    photo_reference: str | None
    recipient_signature: str | None
    carrier_note: str


class Resolution(Record):
    resolution_id: str
    order_id: str
    seller_id: str
    type: Literal["carrier_investigation_request", "refund"]
    status: str
    created_at: datetime
    amount_cents: int | None = None


class Evidence(Record):
    """Facts returned by tools, stored in graph state."""

    observations: dict[str, dict] = Field(default_factory=dict)
    policies: dict[str, dict] = Field(default_factory=dict)

    def references(self) -> set[str]:
        references = set()
        record_types = {
            "order": ("orders", "order_id"),
            "tracking": ("tracking", "tracking_id"),
        }

        for tool_name, result in self.observations.items():
            if "error" in result:
                references.add(f"tool:{tool_name}.error")

            for key, (collection, identifier) in record_types.items():
                if key in result:
                    record = result[key]
                    references.update(
                        f"{collection}:{record[identifier]}.{field}" for field in record
                    )

            for record in result.get("resolutions", []):
                references.update(
                    f"resolutions:{record['resolution_id']}.{field}" for field in record
                )

        return references


class Eligibility(Record):
    decision: Decision
    rule_id: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class RuleRef(Record):
    rule_id: str
    version: str
    source_type: SourceType


class ProposedAction(Record):
    proposal_id: str
    action: Action = "submit_carrier_investigation_request"
    order_id: str
    reason: str
    evidence_refs: list[str]
    policy_version: str


class Recommendation(Record):
    case_id: str
    decision: Decision
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    policy_refs: list[RuleRef] = Field(default_factory=list)
    rule_refs: list[RuleRef] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    proposed_action: ProposedAction | None = None
    approval_required: bool = False
    buyer_reply_draft: str | None = None


class ModelAssessment(Record):
    """The model selects a decision and cites its sources; Python derives actions."""

    decision: Decision
    evidence_refs: list[str]
    policy_rule_ids: list[str]
