"""Workflow steps; assessment facts live in graph state, not the tools object."""

import json

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import ValidationError

from seller_support.assessment import (
    AssessmentError,
    assemble_recommendation,
    assess_observations,
    preflight,
    validate_assessment,
)
from seller_support.models import Evidence, ModelAssessment
from seller_support.tools import ReadTools


class AssessmentNodes:
    def __init__(
        self,
        *,
        tools: ReadTools,
        agent_model=None,
        final_model=None,
        model_factory=None,
        max_model_calls: int = 8,
        max_tool_calls: int = 16,
    ):
        self.tools = tools
        self.agent_model = agent_model
        self.final_model = final_model
        self.model_factory = model_factory
        self.max_model_calls = max_model_calls
        self.max_tool_calls = max_tool_calls
        self.definitions = {tool.name: tool for tool in tools.definitions}

    def preflight(self, state):
        case = self.tools.case
        eligibility = preflight(
            case=case,
            order=self.tools.authorised_order(case.order_id),
            policies=self.tools.policies,
        )
        initial = {
            "evidence": Evidence(),
            "trace": [],
            "model_calls": 0,
            "tool_calls": 0,
            "validation_attempts": 0,
            "recommendation": None,
            "error": None,
        }
        if eligibility:
            initial["recommendation"] = assemble_recommendation(
                case=case,
                eligibility=eligibility,
                policies=self.tools.policies,
            )
            return initial

        path = self.tools.store.root / "instructions" / "seller-support-agent.md"
        initial["messages"] = [
            SystemMessage(content=path.read_text(encoding="utf-8")),
            HumanMessage(
                content=json.dumps(
                    {
                        "order_id": case.order_id,
                        "seller_message": case.seller_message,
                        "evaluation_time": case.evaluation_time.isoformat(),
                    }
                )
            ),
        ]
        return initial

    def agent(self, state):
        if state["model_calls"] >= self.max_model_calls:
            return {"error": "Model iteration limit reached; no recommendation released."}
        if self.agent_model is None and self.model_factory:
            self.agent_model, self.final_model = self.model_factory(self.tools.definitions)
        if self.agent_model is None:
            return {"error": "No model configured."}
        response = self.agent_model.invoke(state["messages"])
        return {
            "messages": [response],
            "model_calls": state["model_calls"] + 1,
        }

    def execute_tools(self, state):
        evidence = state["evidence"].model_copy(deep=True)
        update = {
            "evidence": evidence,
            "messages": [],
            "trace": list(state["trace"]),
            "tool_calls": state["tool_calls"],
        }
        for call in state["messages"][-1].tool_calls:
            if update["tool_calls"] >= self.max_tool_calls:
                return {**update, "error": "Tool-call limit reached; no recommendation released."}
            tool_name = call["name"]
            definition = self.definitions.get(tool_name)
            if definition is None:
                return {
                    **update,
                    "error": "Model requested an unavailable tool; no action executed.",
                }
            try:
                payload = dict(definition.invoke(call["args"]))
            except ValidationError:
                return {**update, "error": "Invalid tool arguments; no recommendation released."}

            attempts = payload.pop("_attempts", 1)
            update["tool_calls"] += 1
            event = {
                "tool": tool_name,
                "attempts": attempts,
                "status": payload.get("error", "ok"),
            }

            # Collect retrieved rules for citation validation.
            if tool_name == "retrieve_policy":
                rules = payload.get("rules", [])
                evidence.policies.update({rule["rule_id"]: rule for rule in rules})
                event["rule_ids"] = [rule["rule_id"] for rule in rules]

            # Collect order-specific tool results for eligibility validation.
            elif call["args"]["order_id"] == self.tools.case.order_id:
                evidence.observations[tool_name] = payload

            update["trace"].append(event)
            update["messages"].append(
                ToolMessage(
                    content=json.dumps(payload),
                    name=tool_name,
                    tool_call_id=call["id"],
                )
            )
        return update

    def finalise(self, state):
        if self.final_model is None:
            return {"error": "No structured-output model configured."}
        evidence = state["evidence"]
        context = {
            "task": "Return the structured assessment using the available sources.",
            "available_evidence_refs": sorted(evidence.references()),
            "retrieved_policy_ids": sorted(evidence.policies),
        }
        try:
            response = self.final_model.invoke(
                [
                    *state["messages"],
                    HumanMessage(content=json.dumps(context)),
                ]
            )
            draft = ModelAssessment.model_validate(response)
            eligibility = assess_observations(evidence)
            validate_assessment(
                draft=draft,
                eligibility=eligibility,
                evidence=evidence,
                policies=self.tools.policies,
            )
        except (AssessmentError, ValidationError, OutputParserException) as exc:
            error = str(exc) if isinstance(exc, AssessmentError) else "Invalid assessment schema."
            if state["validation_attempts"] == 1:
                return {"error": error}
            return {
                "validation_attempts": 1,
                "trace": [*state["trace"], {"stage": "validation_feedback", "error": error}],
                "messages": [
                    HumanMessage(
                        content=(
                            f"Your structured assessment was rejected: {error} "
                            "Retrieve missing facts/policy by exact rule ID if needed, then reassess once."
                        )
                    )
                ],
            }
        return {
            "recommendation": assemble_recommendation(
                case=self.tools.case,
                eligibility=eligibility,
                policies=self.tools.policies,
            )
        }
