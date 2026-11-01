import pytest

from seller_support.graph.builder import build_graph
from seller_support.tools import INACCESSIBLE_MESSAGE


@pytest.mark.parametrize("case_id", ["CASE-007", "CASE-008"])
def test_unknown_and_unowned_orders_are_indistinguishable(make_tools, case_id):
    tools = make_tools(case_id)

    def unexpected_model_creation(definitions):
        raise AssertionError("Denied cases must not initialise an LLM or contact AWS")

    state = build_graph(
        tools=tools,
        model_factory=unexpected_model_creation,
    ).invoke({})
    result = state["recommendation"]
    assert result.summary == INACCESSIBLE_MESSAGE
    assert not result.evidence_refs
    assert not state["trace"]
    for name in ("get_order", "get_tracking", "get_resolution_history"):
        response = tools.read(name, tools.case.order_id)
        assert response == {"error": "order_unavailable", "message": INACCESSIBLE_MESSAGE}


def test_tools_cannot_switch_to_another_order_even_if_same_seller(make_tools):
    response = make_tools().read("get_tracking", "SG-1043")
    assert response["error"] == "order_unavailable"


def test_overrides_do_not_bypass_ownership(make_tools):
    tools = make_tools("CASE-008")
    tools.case.tool_overrides = {"get_tracking": {"patch": {"carrier_note": "leak"}}}
    assert tools.read("get_tracking", "SG-2042")["error"] == "order_unavailable"
