"""SSO-only Bedrock models for tool selection and structured assessment."""

import os

import boto3
from botocore.config import Config
from langchain_aws import ChatBedrockConverse

from seller_support.models import ModelAssessment


def create_models(definitions):
    """
    Return (tool selector, structured assessor), sharing one Bedrock model/client.
    The selector requests our application tools; Python executes them separately.
    The assessor returns ModelAssessment without exposing those application tools.
    It uses the schema as an output tool internally, then parses its arguments.
    Neither runnable calls Bedrock until invoked.
    """
    model = os.getenv("BEDROCK_MODEL_ID", "").strip()
    profile = os.getenv("AWS_PROFILE", "").strip()
    if not model or not profile:
        raise ValueError("AWS_PROFILE (SSO) and BEDROCK_MODEL_ID must be set in .env.")

    session = boto3.Session(profile_name=profile)
    credentials = session.get_credentials()
    if credentials is None or credentials.method != "sso":
        raise ValueError(
            "AWS_PROFILE must resolve directly to an IAM Identity Center (SSO) profile."
        )

    client = session.client(
        "bedrock-runtime",
        region_name=session.region_name,
        config=Config(
            connect_timeout=10,
            read_timeout=45,
            retries={
                "total_max_attempts": 2,
                "mode": "standard",
            },
        ),
    )
    llm = ChatBedrockConverse(
        model_id=model,
        client=client,
        region_name=session.region_name,
        max_tokens=2048,
        disable_streaming=True,
    )
    return llm.bind_tools(definitions), llm.with_structured_output(ModelAssessment)
