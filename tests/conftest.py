import json
from pathlib import Path

import pytest

from rebalancer.adapters import load_demo
from rebalancer.engine import evaluate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def golden():
    return json.loads((FIXTURES / "golden_valuation.json").read_text())


@pytest.fixture(scope="session")
def demo():
    ds, issues = load_demo()
    return ds, issues


@pytest.fixture(scope="session")
def result(demo):
    return evaluate(demo[0], issues=demo[1])


@pytest.fixture(scope="session")
def by_client(result):
    return {c.name: c for c in result.clients}
