from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from seller_support.models import Evidence, Recommendation


class AssessmentState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    evidence: Evidence
    trace: list[dict]
    model_calls: int
    tool_calls: int
    validation_attempts: int
    recommendation: Recommendation | None
    error: str | None
