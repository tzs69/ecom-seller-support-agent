import shutil

from conftest import ROOT

from seller_support.assessment import assess_observations, preflight
from seller_support.models import Evidence
from seller_support.retrieval import PolicyCorpus


def test_only_business_rules_are_retrievable(make_tools):
    tools = make_tools()
    assert set(tools.policies.rules) == {
        "SCOPE-02",
        "EVIDENCE-01",
        "EVIDENCE-02",
        "EVIDENCE-03",
        "HISTORY-01",
    }
    result = tools.retrieve("ACCESS-02 ACTION-01 expected answers")
    assert all(rule["source_type"] == "business_policy" for rule in result["rules"])
    assert all(rule["source"].startswith("policies/") for rule in result["rules"])


def test_future_policy_cannot_be_used(make_tools):
    tools = make_tools()
    earlier = tools.case.evaluation_time.replace(year=2025)
    policies = PolicyCorpus(ROOT, "SG", earlier)
    assert not policies.supported
    assert not policies.rules


def test_missing_required_policy_fails_closed(make_tools, tmp_path):
    tools = make_tools()
    shutil.copytree(ROOT / "policies", tmp_path / "policies")
    (tmp_path / "policies" / "03-existing-resolutions.md").unlink()
    policies = PolicyCorpus(tmp_path, "SG", tools.case.evaluation_time)
    result = preflight(
        case=tools.case,
        order=tools.authorised_order(tools.case.order_id),
        policies=policies,
    )
    assert result.decision == "insufficient_evidence"


def test_unknown_location_is_not_a_mismatch(make_tools):
    tools = make_tools()
    tools.case.tool_overrides = {"get_tracking": {"patch": {"delivery_location_token": None}}}
    evidence = Evidence(
        observations={
            name: tools.read(name, tools.case.order_id)
            for name in ("get_order", "get_resolution_history", "get_tracking")
        }
    )
    assert assess_observations(evidence).decision == "propose_carrier_investigation"
