from pathlib import Path
from uuid import uuid4

import pytest

from seller_support.fixtures import FixtureStore
from seller_support.retrieval import PolicyCorpus
from seller_support.tools import ReadTools

ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    # Do not reuse a directory created under another Windows/sandbox identity:
    # pytest deletes a fixed --basetemp on startup, which can fail on its ACLs.
    # A fresh directory also isolates concurrent test runs. Honour explicit CLI overrides.
    if config.option.basetemp is None:
        parent = ROOT / "runtime" / "pytest-runs"
        parent.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(parent / f"run-{uuid4().hex}")


@pytest.fixture
def store():
    return FixtureStore(ROOT)


@pytest.fixture
def make_tools(store):
    def make(case_id="CASE-001"):
        case = store.load_case(case_id)
        order = store.orders.get(case.order_id)
        market = order.market if order and order.seller_id == case.authenticated_seller_id else ""
        return ReadTools(case, store, PolicyCorpus(ROOT, market, case.evaluation_time))

    return make
