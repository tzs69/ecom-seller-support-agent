"""Synthetic backend data and scenario-specific transport failures."""

import json
from pathlib import Path

from seller_support.models import CaseInput, Order, Resolution, Tracking

TRANSIENT_ERRORS = {"timeout", "temporarily_unavailable"}


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class FixtureStore:
    def __init__(
        self,
        root: Path,
    ):
        self.root = root.resolve()
        self.orders = {
            record["order_id"]: Order.model_validate(record) for record in self._read("orders")
        }
        self.tracking = {
            record["tracking_id"]: Tracking.model_validate(record)
            for record in self._read("tracking")
        }
        self.resolutions = [
            Resolution.model_validate(record) for record in self._read("resolutions")
        ]

    def _read(self, name: str):
        path = self.root / "data" / f"{name}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def list_cases(self) -> list[dict]:
        return self._read("cases")["cases"]

    def load_case(self, case_id: str) -> CaseInput:
        document = self._read("cases")
        for case in document["cases"]:
            if case["case_id"] == case_id:
                return CaseInput.model_validate({**document["defaults"], **case})
        raise ValueError(f"Unknown scenario: {case_id}")

    def read(
        self,
        name: str,
        order: Order,
        overrides: dict,
    ) -> dict:
        """Called only after tool authorisation. Retry transient failures once."""
        override = overrides.get(name, {})
        for attempt in (1, 2):
            error = override.get("error")
            if error not in TRANSIENT_ERRORS or attempt == 2:
                break
            if not override.get("all_attempts", True):
                override = {}

        if error:
            return {"error": error, "_attempts": attempt}

        if name == "get_order":
            result = {"order": order.model_dump(mode="json")}
        elif name == "get_resolution_history":
            result = {
                "resolutions": [
                    record.model_dump(mode="json")
                    for record in self.resolutions
                    if record.order_id == order.order_id and record.seller_id == order.seller_id
                ]
            }
        elif name == "get_tracking":
            record = self.tracking.get(order.tracking_id)
            if record is None:
                return {"error": "tracking_unavailable", "_attempts": attempt}
            patched = {
                **record.model_dump(mode="json"),
                **override.get("patch", {}),
            }
            result = {"tracking": Tracking.model_validate(patched).model_dump(mode="json")}
        else:
            raise ValueError(f"Unknown fixture operation: {name}")

        return {**result, "_attempts": attempt}
