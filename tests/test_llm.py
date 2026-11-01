import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import NoRegionError
from botocore.stub import Stubber
from langchain_core.messages import HumanMessage

from seller_support.llm import create_models
from seller_support.models import ModelAssessment

MODEL = (
    "anthropic.claude-3-haiku-20240307-v1:0"  # Offline schema fixture, not a model recommendation.
)


@pytest.fixture(autouse=True)
def isolated_aws(monkeypatch, tmp_path):
    for name in (
        "BEDROCK_MODEL_ID",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "config"))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "credentials"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")


def configure(monkeypatch, profile_region="eu-west-1", explicit_region=True):
    # SSO metadata only: the SDK's lazy SSO provider needs no token for these
    # constructor/parser tests. Stubber intercepts inference before signing.
    region_line = f"region = {profile_region}\n" if profile_region else ""
    Path(os.environ["AWS_CONFIG_FILE"]).write_text(
        "[profile portfolio]\nsso_session = portfolio-session\n"
        "sso_account_id = 123456789012\nsso_role_name = BedrockDeveloper\n"
        + region_line
        + "[sso-session portfolio-session]\n"
        "sso_start_url = https://example.awsapps.com/start\nsso_region = us-east-1\n"
    )
    monkeypatch.setenv("BEDROCK_MODEL_ID", MODEL)
    monkeypatch.setenv("AWS_PROFILE", "portfolio")
    if explicit_region:
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")


def test_configuration_requires_model(monkeypatch, make_tools):
    with pytest.raises(ValueError, match="BEDROCK_MODEL_ID"):
        create_models(make_tools().definitions)


def test_configuration_requires_region(monkeypatch, make_tools):
    configure(monkeypatch, profile_region=None, explicit_region=False)
    with pytest.raises(NoRegionError):
        create_models(make_tools().definitions)


def test_bedrock_tools_and_structured_parser_with_stubbed_sdk(monkeypatch, make_tools):
    configure(monkeypatch)
    agent, final = create_models(make_tools().definitions)
    assert {tool["function"]["name"] for tool in agent.kwargs["tools"]} == {
        "get_order",
        "get_tracking",
        "get_resolution_history",
        "retrieve_policy",
    }
    assert "parallel_tool_calls" not in agent.kwargs
    client = agent.bound.client
    assert client.meta.config.retries["total_max_attempts"] == 2
    draft = ModelAssessment(decision="insufficient_evidence", evidence_refs=[], policy_rule_ids=[])

    def response(name, arguments):
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "stub-call",
                                "name": name,
                                "input": arguments,
                            }
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
            "metrics": {"latencyMs": 1},
        }

    with Stubber(client) as stub:
        # Inspect actual Bedrock request conversion, not only Pydantic's source
        # schema: the adapter strips null unions before sending tool definitions.
        outgoing_schemas = []

        def capture_schema(params, **kwargs):
            outgoing_schemas.extend(
                spec["toolSpec"]["inputSchema"]["json"]
                for spec in params.get("toolConfig", {}).get("tools", [])
                if spec.get("toolSpec", {}).get("name") == "ModelAssessment"
            )

        client.meta.events.register(
            "before-parameter-build.bedrock-runtime.Converse", capture_schema
        )
        stub.add_response("converse", response("get_order", {"order_id": "SG-1042"}))
        stub.add_response("converse", response("ModelAssessment", draft.model_dump()))
        chosen = agent.invoke([HumanMessage(content="Assess SG-1042")])
        assert chosen.tool_calls[0]["name"] == "get_order"
        assert final.invoke([HumanMessage(content="Return the assessment")]) == draft
        assert set(outgoing_schemas[0]["properties"]) == {
            "decision",
            "evidence_refs",
            "policy_rule_ids",
        }
        stub.assert_no_pending_responses()


def test_named_profile_and_profile_region_are_used(monkeypatch, make_tools):
    configure(monkeypatch, explicit_region=False)
    agent, _ = create_models(make_tools().definitions)
    assert agent.bound.region_name == "eu-west-1"
    assert agent.bound.client._request_signer._credentials.method == "sso"


def test_explicit_region_takes_precedence(monkeypatch, make_tools):
    configure(monkeypatch)
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")
    agent, _ = create_models(make_tools().definitions)
    assert agent.bound.region_name == "eu-west-1"


def test_configuration_requires_explicit_sso_profile(monkeypatch, make_tools):
    monkeypatch.setenv("BEDROCK_MODEL_ID", MODEL)
    with pytest.raises(ValueError, match="BEDROCK_MODEL_ID"):
        create_models(make_tools().definitions)


@pytest.mark.parametrize("method", ["shared-credentials-file", "iam-role", "env"])
def test_non_sso_profiles_are_rejected_before_client_creation(monkeypatch, make_tools, method):
    monkeypatch.setenv("BEDROCK_MODEL_ID", MODEL)
    monkeypatch.setenv("AWS_PROFILE", "not-sso")
    session = SimpleNamespace(
        region_name="us-east-1", get_credentials=lambda: SimpleNamespace(method=method)
    )
    monkeypatch.setattr("seller_support.llm.boto3.Session", lambda **kwargs: session)
    with pytest.raises(ValueError, match="must resolve directly.*SSO"):
        create_models(make_tools().definitions)
