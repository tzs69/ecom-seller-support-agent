"""Business eligibility, model validation, and final response assembly."""

from uuid import uuid4

from seller_support.models import (
    INACCESSIBLE_MESSAGE,
    CaseInput,
    Eligibility,
    Evidence,
    ModelAssessment,
    Order,
    ProposedAction,
    Recommendation,
    RuleRef,
)
from seller_support.retrieval import PolicyCorpus


class AssessmentError(ValueError):
    """The model's decision or sources do not match the observed facts."""


def preflight(
    *,
    case: CaseInput,
    order: Order | None,
    policies: PolicyCorpus,
) -> Eligibility | None:
    if not case.order_id:
        return Eligibility(
            decision="needs_order_id",
            rule_id="ACCESS-01",
            summary="Please provide the order ID.",
        )
    if order is None:
        return Eligibility(
            decision="order_unavailable",
            rule_id="ACCESS-02",
            summary=INACCESSIBLE_MESSAGE,
        )
    if not policies.supported:
        return Eligibility(
            decision="unsupported_policy_scope",
            rule_id="SCOPE-01",
            summary="No policy covers this market and date. Human handoff is required.",
            evidence_refs=[f"orders:{order.order_id}.market"],
        )
    if not policies.complete:
        return Eligibility(
            decision="insufficient_evidence",
            rule_id="EVIDENCE-04",
            summary="Required business policy is unavailable.",
            missing_information=["applicable business policy"],
        )
    if order.status != "delivered":
        return Eligibility(
            decision="outside_workflow",
            rule_id="SCOPE-02",
            summary=f"Order status is {order.status}; this needs a different support workflow.",
            evidence_refs=[f"orders:{order.order_id}.status"],
        )
    return None


def assess_observations(evidence: Evidence) -> Eligibility:
    """Derive the permitted outcome from tool results, independently of the model.

    Return the first applicable decision and its supporting references. Missing
    required tool calls raise AssessmentError; failed lookups yield insufficient
    evidence. No model answer or evaluation labels are read.

    Checks in priority order:
        1. Require successful order and resolution-history results.
        2. Return existing_resolution for a completed refund or open carrier
           request, displaying the refund first if both exist.
        3. Return human_review for any other previous carrier request.
        4. Require a successful tracking result before assessing delivery proof.
        5. Return insufficient_evidence if order and tracking statuses disagree.
        6. Return human_review for a known delivery-location mismatch.
        7. Propose a carrier investigation if photo and signature are both absent;
           otherwise return human_review for disputed receipt with available proof.
    """
    observed = evidence.observations

    # 1. Establish order/history before deciding whether tracking is needed.
    for name in ("get_order", "get_resolution_history"):
        if name not in observed:
            raise AssessmentError(f"Required tool result missing: {name}")
        if "error" in observed[name]:
            return Eligibility(
                decision="insufficient_evidence",
                rule_id="EVIDENCE-04",
                summary=f"{name} is unavailable; no action is proposed.",
                evidence_refs=[f"tool:{name}.error"],
                missing_information=[name],
            )

    # 2. Existing resolutions block a new request; display a completed refund first.
    order = observed["get_order"]["order"]
    history = observed["get_resolution_history"]["resolutions"]
    refunds = [
        record
        for record in history
        if (record["type"] == "refund" and record["status"] == "completed")
    ]
    requests = [record for record in history if record["type"] == "carrier_investigation_request"]
    open_requests = [record for record in requests if record["status"] == "open"]
    if refunds or open_requests:
        record = (refunds or open_requests)[0]
        return Eligibility(
            decision="existing_resolution",
            rule_id="HISTORY-01",
            summary=(
                f"Existing {record['type']} {record['resolution_id']} has status {record['status']}. "
                "No new carrier investigation request is proposed."
            ),
            evidence_refs=[f"resolutions:{record['resolution_id']}.status"],
        )

    # 3. Any remaining previous carrier request requires human review.
    if requests:
        return Eligibility(
            decision="human_review",
            rule_id="HISTORY-01",
            summary="A previous carrier request needs human review; no second request is allowed.",
            evidence_refs=[f"resolutions:{requests[0]['resolution_id']}.status"],
        )

    # 4. Require tracking now; a failed lookup is not evidence of absent proof.
    if "get_tracking" not in observed:
        raise AssessmentError("Required tool result missing: get_tracking")
    result = observed["get_tracking"]
    if "error" in result:
        return Eligibility(
            decision="insufficient_evidence",
            rule_id="EVIDENCE-04",
            summary="Tracking is unavailable. Delivery proof cannot be assessed; no action is proposed.",
            evidence_refs=["tool:get_tracking.error"],
            missing_information=["carrier tracking"],
        )

    # 5. Contradictory statuses prevent a reliable delivery assessment.
    tracking = result["tracking"]
    order_ref = f"orders:{order['order_id']}"
    tracking_ref = f"tracking:{tracking['tracking_id']}"
    if tracking["status"] != order["status"]:
        return Eligibility(
            decision="insufficient_evidence",
            rule_id="EVIDENCE-04",
            summary="Order and tracking statuses disagree; human review is needed.",
            evidence_refs=[f"{order_ref}.status", f"{tracking_ref}.status"],
            missing_information=["consistent delivery status"],
        )

    # 6. A known location conflict takes precedence over absent photo/signature.
    location = tracking["delivery_location_token"]
    if location is not None and location != order["destination_token"]:
        return Eligibility(
            decision="human_review",
            rule_id="EVIDENCE-02",
            summary=(
                "The delivery location differs from the destination. "
                "Human review is required; fault is not established."
            ),
            evidence_refs=[
                f"{order_ref}.destination_token",
                f"{tracking_ref}.delivery_location_token",
            ],
        )

    # 7. Both proof fields absent permits a proposal; otherwise require human review.
    proof_refs = [
        f"{order_ref}.status",
        f"{tracking_ref}.photo_reference",
        f"{tracking_ref}.recipient_signature",
    ]
    if tracking["photo_reference"] is None and tracking["recipient_signature"] is None:
        return Eligibility(
            decision="propose_carrier_investigation",
            rule_id="EVIDENCE-01",
            summary=(
                "Delivery is recorded, but no photo or recipient signature is available. "
                "A carrier investigation request is proposed and requires seller approval. "
                "Nothing has been submitted."
            ),
            evidence_refs=proof_refs,
            missing_information=["proof of buyer receipt"],
        )

    return Eligibility(
        decision="human_review",
        rule_id="EVIDENCE-03",
        summary=(
            "Delivery proof references exist, but receipt is disputed. "
            "Human review is required; the proof is not visually verified."
        ),
        evidence_refs=proof_refs,
    )


def validate_assessment(
    *,
    draft: ModelAssessment,
    eligibility: Eligibility,
    evidence: Evidence,
    policies: PolicyCorpus,
) -> None:
    """Reject a model draft that disagrees with the evidence-derived eligibility.

    Return None on success; raise AssessmentError for correction or termination.

    Checks in order:
        1. Require the model's decision to match the independently derived outcome.
        2. Require the governing business rule, if any, among policy citations,
           and require every cited policy to have been retrieved. Backend controls
           are not business-policy citations.
        3. Require all supporting evidence references from eligibility, and reject
           citations absent from observed tool results. Extra observed references
           are allowed; this checks their existence, not their relevance.
    """
    # 1. Match the decision against the independent Python assessment.
    if draft.decision != eligibility.decision:
        raise AssessmentError(
            f"Decision: got {draft.decision!r}, expected {eligibility.decision!r}."
        )

    # 2. Include the required business rule; all policy citations must be retrieved.
    required = {eligibility.rule_id} if eligibility.rule_id in policies.rules else set()
    cited = set(draft.policy_rule_ids)
    if not required <= cited or not cited <= evidence.policies.keys():
        raise AssessmentError(
            f"Business policy missing or not retrieved. Required: {sorted(required)}; "
            f"cited: {sorted(cited)}; retrieved: {sorted(evidence.policies)}."
        )

    # 3. Include required evidence fields; additional citations must exist in observations.
    missing = set(eligibility.evidence_refs) - set(draft.evidence_refs)
    unknown = set(draft.evidence_refs) - evidence.references()
    if missing or unknown:
        raise AssessmentError(
            f"Evidence references: missing {sorted(missing)}; unknown {sorted(unknown)}."
        )


def assemble_recommendation(
    *,
    case: CaseInput,
    eligibility: Eligibility,
    policies: PolicyCorpus,
) -> Recommendation:
    """Actions and approval flags are derived here, never guessed by the model."""
    rule = policies.rules.get(eligibility.rule_id)
    if rule:
        primary_ref = rule.reference()
    else:
        primary_ref = RuleRef(
            rule_id=eligibility.rule_id,
            version="1.0",
            source_type="agent_instruction"
            if eligibility.rule_id == "ACCESS-01"
            else "backend_control",
        )

    output = Recommendation(
        case_id=case.case_id,
        decision=eligibility.decision,
        summary=eligibility.summary,
        evidence_refs=eligibility.evidence_refs,
        missing_information=eligibility.missing_information,
        policy_refs=[primary_ref] if rule else [],
        rule_refs=[primary_ref],
    )
    if eligibility.decision == "propose_carrier_investigation":
        output.rule_refs.append(
            RuleRef(
                rule_id="ACTION-01",
                version="1.0",
                source_type="backend_control",
            )
        )
        output.proposed_action = ProposedAction(
            proposal_id=f"P-{uuid4().hex}",
            order_id=case.order_id,
            reason=eligibility.summary,
            evidence_refs=eligibility.evidence_refs,
            policy_version=policies.rules["EVIDENCE-01"].version,
        )
        output.approval_required = True
    return output
