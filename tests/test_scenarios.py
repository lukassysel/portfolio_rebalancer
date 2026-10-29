"""Scenario oracles for the five demo clients (doc 08 §15, doc 10 §1). Nothing here is hardcoded in the engine:
the engine regenerates these results from rules + inputs."""

import json
from decimal import Decimal as D
from pathlib import Path

import pytest

EXPECTED = json.loads((Path(__file__).parent / "fixtures" / "expected_v23.json").read_text())["clients"]
CENT = D("0.01")


@pytest.fixture(scope="module")
def by_client(demo):
    """The verified oracles fix the contract rules: no minimum cash buffer and no merging of later top-ups
    (both are policy settings added later; their defaults are tested separately)."""
    from dataclasses import replace
    from rebalancer.engine import evaluate
    from rebalancer.engine.policy import default_policy
    ds, issues = demo
    pols = {c.name: replace(default_policy(c.targets), min_cash_pct=D(0), min_cash_czk=D(0))
            for c in ds.clients}
    return {c.name: c for c in evaluate(ds, pols, issues=issues).clients}


def alt(client, alt_id):
    return next(a for a in client.alternatives if a.id == alt_id)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_recommendation_and_orders(by_client, name):
    exp, c = EXPECTED[name], by_client[name]
    assert c.status == "ok"
    assert c.recommended == exp["recommended"]
    assert c.outcome.code == exp["outcome"]
    if "outcome_date" in exp:
        assert c.outcome.date.isoformat() == exp["outcome_date"]
    a = alt(c, exp["recommended"])
    got = [[o.trade_date.isoformat(), o.side, o.ticker, o.units] for o in a.orders]
    assert got == exp["orders"]
    assert a.total_cost.quantize(CENT) == D(exp["total"])
    if "commissions" in exp:
        assert a.commissions.quantize(CENT) == D(exp["commissions"])
        assert a.fx_cost.quantize(CENT) == D(exp["fx"])
    if "tax" in exp:
        assert (a.tax or D(0)).quantize(CENT) == D(exp["tax"])


def test_e_now_versus_wait(by_client):
    e = by_client["Klient E"]
    now = alt(e, "NOW_P")
    assert now.total_cost.quantize(CENT) == D(EXPECTED["Klient E"]["now_p_total"])
    assert now.tax.quantize(CENT) == D(EXPECTED["Klient E"]["now_p_tax15"])
    assert now.tax_high.quantize(CENT) == D(EXPECTED["Klient E"]["now_p_tax23"])
    wt = alt(e, "WAIT_TAX_P").wait_test
    assert wt.passed and wt.days == 31 and wt.max_deviation <= 15
    # FIFO split of the exempt sale on 23 Nov: 122 units from 2020 lot (rest sold on 23 Oct) + 472 from 2023 lot
    sale = next(o for o in alt(e, "WAIT_TAX_P").orders if o.trade_date.isoformat() == "2026-11-23" and o.side == "SELL")
    assert [(l.acquired.isoformat(), l.units, l.exempt) for l in sale.lots] == [("2020-01-13", 122, True),
                                                                              ("2023-11-20", 472, True)]


def test_a_wait_for_deposit_fails_waiting_test(by_client):
    a = by_client["Klient A"]
    for i in ("WAIT_DEP_P", "WAIT_DEP_T"):
        assert not alt(a, i).wait_test.passed


def test_deposit_steps_are_conditional(by_client):
    a = alt(by_client["Klient A"], "NOW_P")
    later = [o for o in a.orders if o.trade_date.isoformat() == "2026-11-10"]
    assert later and all(o.conditional and o.step_reason == "deposit" for o in later)
    assert not any(o.conditional for o in a.orders if o.trade_date.isoformat() == "2026-10-23")


def test_b_liquidity_trigger(by_client):
    b = by_client["Klient B"]
    l1 = [t for t in b.triggers if t.rule == "L1"]
    assert l1 and l1[0].date.isoformat() == "2027-01-15"
    assert not alt(b, "BASE").feasible


def test_d_corporate_tax_not_determinable(by_client):
    d = by_client["Klient D"]
    for a in d.alternatives:  # s.r.o.: tax unknown when something is sold, 0 when nothing is
        sells = any(o.side == "SELL" for o in a.orders)
        assert (a.tax is None) if sells else (a.tax == 0)


def test_c_positive_reason(by_client):
    c = by_client["Klient C"]
    assert c.outcome.code == "no_action" and c.monitoring == []
    assert c.valuation.max_abs_deviation < D("0.5")
