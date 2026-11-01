"""Exercise the real graph with scripted models, never paid inference."""

import json
from uuid import uuid4

import pytest
from conftest import ROOT
from langchain_core.messages import AIMessage, ToolMessage

from seller_support.assessment import (
    AssessmentError,
    assess_observations,
    validate_assessment,
)
from seller_support.graph.builder import build_graph
from seller_support.models import Evidence, ModelAssessment


def evidence_from(messages) -> Evidence:
    evidence = Evidence()
    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        payload = json.loads(message.content)
        if message.name == "retrieve_policy":
            evidence.policies.update({rule["rule_id"]: rule for rule in payload.get("rules", [])})
        else:
            evidence.observations[message.name] = payload
    return evidence


def tool_call(name, arguments) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": arguments,
                "id": uuid4().hex,
                "type": "tool_call",
            }
        ],
    )


class ScriptedAgent:
    def __init__(
        self,
        tools,
    ):
        self.case = tools.case

    def invoke(self, messages):
        evidence = evidence_from(messages)
        observed = evidence.observations
        order = {"order_id": self.case.order_id}
        if "get_order" not in observed:
            return tool_call("get_order", order)
        if "get_resolution_history" not in observed:
            return tool_call("get_resolution_history", order)

        history = observed["get_resolution_history"].get("resolutions", [])
        if not history and "get_tracking" not in observed:
            return tool_call("get_tracking", order)
        if not evidence.policies:
            query = "HISTORY-01" if history else "EVIDENCE-01 EVIDENCE-02 EVIDENCE-03"
            return tool_call("retrieve_policy", {"query": query})
        return AIMessage(content="Ready for structured assessment.")


class ScriptedFinal:
    def __init__(
        self,
        tools,
    ):
        self.policies = tools.policies

    def invoke(self, messages):
        result = assess_observations(evidence_from(messages))
        return ModelAssessment(
            decision=result.decision,
            evidence_refs=result.evidence_refs,
            policy_rule_ids=[result.rule_id] if result.rule_id in self.policies.rules else [],
        )


LABELS = json.loads((ROOT / "evals" / "expected_resolutions.json").read_text())["cases"]


@pytest.mark.parametrize("label", LABELS, ids=lambda label: label["case_id"])
def test_graph_matches_case_outcomes(make_tools, label):
    tools = make_tools(label["case_id"])
    result = build_graph(
        tools=tools,
        agent_model=ScriptedAgent(tools),
        final_model=ScriptedFinal(tools),
    ).invoke({})

    assert not result.get("error")
    output = result["recommendation"]
    assert output.decision == label["decision"]
    assert output.approval_required == label["approval_required"]
    assert (output.proposed_action.action if output.proposed_action else None) == label[
        "proposed_action"
    ]
    assert set(label["required_rule_ids"]) <= {ref.rule_id for ref in output.rule_refs}
    assert "ACTION-04" not in {ref.rule_id for ref in output.rule_refs}
    assert set(label["required_evidence_refs"]) <= set(output.evidence_refs)

    if label["case_id"] == "CASE-003":
        assert "get_tracking" not in result["evidence"].observations
    if label["case_id"] == "CASE-011":
        tracking_events = [
            event for event in result["trace"] if event.get("tool") == "get_tracking"
        ]
        assert tracking_events[0]["attempts"] == 2
    assert not any(
        event.get("tool") == "submit_carrier_investigation_request" for event in result["trace"]
    )


def gathered(tools) -> Evidence:
    evidence = Evidence()
    for name in ("get_order", "get_resolution_history", "get_tracking"):
        payload = tools.read(name, tools.case.order_id)
        payload.pop("_attempts", None)
        evidence.observations[name] = payload
    evidence.policies = {rule["rule_id"]: rule for rule in tools.retrieve("EVIDENCE-01")["rules"]}
    return evidence


def validate(tools, evidence, draft):
    return validate_assessment(
        draft=draft,
        eligibility=assess_observations(evidence),
        evidence=evidence,
        policies=tools.policies,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"decision": "human_review"},
        {"evidence_refs": ["tracking:invented.photo_reference"]},
        {"policy_rule_ids": ["ACTION-01"]},
    ],
)
def test_guard_rejects_unsupported_model_assessments(make_tools, changes):
    tools = make_tools()
    evidence = gathered(tools)
    result = assess_observations(evidence)
    draft = ModelAssessment(
        decision=result.decision,
        evidence_refs=result.evidence_refs,
        policy_rule_ids=[result.rule_id],
    )
    with pytest.raises(AssessmentError):
        validate(tools, evidence, draft.model_copy(update=changes))


def test_missing_tool_results_cannot_be_replaced_with_model_guesses():
    with pytest.raises(AssessmentError, match="Required tool result missing"):
        assess_observations(Evidence())


def test_missing_policy_retrieval_rejects_correct_decision(make_tools):
    tools = make_tools()
    evidence = gathered(tools)
    result = assess_observations(evidence)
    draft = ModelAssessment(
        decision=result.decision,
        evidence_refs=result.evidence_refs,
        policy_rule_ids=[result.rule_id],
    )
    evidence.policies.clear()
    with pytest.raises(AssessmentError, match="not retrieved"):
        validate(tools, evidence, draft)


def test_location_conflict_wins_over_missing_proof(make_tools):
    tools = make_tools()
    tools.case.tool_overrides = {"get_tracking": {"patch": {"delivery_location_token": "OTHER"}}}
    result = assess_observations(gathered(tools))
    assert result.decision == "human_review"
    assert result.rule_id == "EVIDENCE-02"


def test_malicious_note_cannot_change_the_verified_output(make_tools):
    tools = make_tools("CASE-012")
    state = build_graph(
        tools=tools,
        agent_model=ScriptedAgent(tools),
        final_model=ScriptedFinal(tools),
    ).invoke({})
    output = state["recommendation"]
    assert output.approval_required is True
    assert "Nothing has been submitted" in output.summary
    assert "SYSTEM OVERRIDE" not in output.summary


def test_model_iteration_limit_stops_the_loop(make_tools):
    tools = make_tools()

    class Loop:
        def invoke(self, messages):
            return tool_call("get_order", {"order_id": "SG-1042"})

    result = build_graph(
        tools=tools,
        agent_model=Loop(),
        max_model_calls=2,
    ).invoke({})
    assert result["recommendation"] is None
    assert "iteration limit" in result["error"]


def test_write_tool_is_unavailable(make_tools):
    class WriteAttempt:
        def invoke(self, messages):
            return tool_call("submit_carrier_investigation_request", {})

    result = build_graph(tools=make_tools(), agent_model=WriteAttempt()).invoke({})
    assert "unavailable tool" in result["error"]
    assert not result["trace"]


def test_tool_call_limit_stops_the_loop(make_tools):
    tools = make_tools()
    result = build_graph(
        tools=tools,
        agent_model=ScriptedAgent(tools),
        final_model=ScriptedFinal(tools),
        max_tool_calls=1,
    ).invoke({})
    assert "Tool-call limit" in result["error"]
    assert result["recommendation"] is None


@pytest.mark.parametrize("eventually_correct", [True, False])
def test_validation_repair_is_bounded(make_tools, eventually_correct):
    tools = make_tools()

    class RepairFinal(ScriptedFinal):
        calls = 0

        def invoke(self, messages):
            self.calls += 1
            draft = super().invoke(messages)
            if not eventually_correct or self.calls == 1:
                return draft.model_copy(update={"decision": "human_review"})
            return draft

    final = RepairFinal(tools)
    result = build_graph(
        tools=tools,
        agent_model=ScriptedAgent(tools),
        final_model=final,
    ).invoke({})
    assert final.calls == 2
    assert result["validation_attempts"] == 1
    if eventually_correct:
        assert result["recommendation"].approval_required is True
        assert result["error"] is None
    else:
        assert result["recommendation"] is None
        assert "Decision" in result["error"]


def test_feedback_can_retrieve_a_missed_history_rule(make_tools):
    tools = make_tools("CASE-003")

    class RetrievalRepair(ScriptedAgent):
        def invoke(self, messages):
            feedback = messages[-1].content
            if isinstance(feedback, str) and feedback.startswith(
                "Your structured assessment was rejected"
            ):
                return tool_call("retrieve_policy", {"query": "HISTORY-01"})
            response = super().invoke(messages)
            if response.tool_calls and response.tool_calls[0]["name"] == "retrieve_policy":
                response.tool_calls[0]["args"]["query"] = "EVIDENCE-01 EVIDENCE-02 EVIDENCE-03"
            return response

    result = build_graph(
        tools=tools,
        agent_model=RetrievalRepair(tools),
        final_model=ScriptedFinal(tools),
    ).invoke({})
    assert result["error"] is None
    assert result["recommendation"].decision == "existing_resolution"
    assert result["recommendation"].proposed_action is None
    assert "HISTORY-01" in result["evidence"].policies
    assert "get_tracking" not in result["evidence"].observations


def test_all_assessment_facts_are_in_graph_state(make_tools):
    tools = make_tools()
    result = build_graph(
        tools=tools,
        agent_model=ScriptedAgent(tools),
        final_model=ScriptedFinal(tools),
    ).invoke({})
    assert "get_order" in result["evidence"].observations
    assert "EVIDENCE-01" in result["evidence"].policies
    assert result["tool_calls"] == 4
    assert len(result["trace"]) == 4
    assert not hasattr(tools, "observations")
