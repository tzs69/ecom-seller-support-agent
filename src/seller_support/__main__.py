"""Run one read-only assessment from the terminal."""

import argparse
import json
import sys
from pathlib import Path

from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

from seller_support.fixtures import FixtureStore, default_project_root
from seller_support.graph.builder import build_graph
from seller_support.llm import create_models
from seller_support.retrieval import PolicyCorpus
from seller_support.tools import ReadTools


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only delivery-dispute assessment")
    parser.add_argument("--case", default="CASE-001")
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--project-root", type=Path)
    parser.add_argument(
        "--trace", action="store_true", help="Print tool/validation events to stderr"
    )
    args = parser.parse_args()
    state = {}

    try:
        root = args.project_root or default_project_root()
        store = FixtureStore(root)
        if args.list_cases:
            for case in store.list_cases():
                print(f"{case['case_id']}: {case['order_id'] or '(no order ID)'}")
            return 0

        load_dotenv(root / ".env", override=False)
        case = store.load_case(args.case)
        order = store.orders.get(case.order_id)
        market = order.market if order and order.seller_id == case.authenticated_seller_id else ""
        policies = PolicyCorpus(root, market, case.evaluation_time)
        tools = ReadTools(
            case=case,
            store=store,
            policies=policies,
        )
        graph = build_graph(tools=tools, model_factory=create_models)
        for state in graph.stream(
            {},
            {"recursion_limit": 40},
            stream_mode="values",  # Entire graph state emitted after every node/step
        ):
            pass

        if state.get("error"):
            print(json.dumps({"error": state["error"], "recommendation": None}), file=sys.stderr)
            return 1
        print(state["recommendation"].model_dump_json(indent=2))
        return 0

    except ClientError as exc:
        error = exc.response["Error"]
        print(f"Bedrock {error['Code']}: {error['Message']}", file=sys.stderr)
        return 1
    except BotoCoreError as exc:
        print(f"AWS: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        if args.trace:
            print(json.dumps({"tool_trace": state.get("trace", [])}), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
