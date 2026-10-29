"""Engine invariants I1–I10 (doc 10 §3), asserted on every alternative of every demo client."""

from collections import defaultdict
from dataclasses import asdict, replace
from decimal import Decimal as D

from rebalancer.engine import default_policies, evaluate


def test_invariants_all_alternatives(demo, result):
    ds = demo[0]
    for c in result.clients:
        client = next(x for x in ds.clients if x.name == c.name)
        start = defaultdict(int)
        for lot in client.lots:
            start[lot.ticker] += lot.units
        for a in c.alternatives:
            held = dict(start)
            bought, sold = set(), set()
            per_day = set()
            for o in a.orders:
                assert isinstance(o.units, int) and o.units > 0  # I1, I10
                key = (o.trade_date, o.side, o.ticker)
                assert key not in per_day  # one order per instrument per day
                per_day.add(key)
                held[o.ticker] += o.units if o.side == "BUY" else -o.units
                assert held[o.ticker] >= 0  # I1
                (bought if o.side == "BUY" else sold).add(o.ticker)
                if o.side == "BUY":
                    assert c.valuation and next(x for x in c.valuation.components if x.key == o.ticker).target > 0  # I6
                else:
                    assert sum(l.units for l in o.lots) == o.units  # I3
            assert not (bought & sold)  # I7 no round trips
            if a.feasible:  # I2 / I5: settled cash ≥ 0 in every currency on every value date
                for p in a.balances:
                    assert all(v >= D("-0.005") for v in p.balances.values()), (c.name, a.id, p)


def test_determinism(demo, result):
    again = evaluate(demo[0], issues=demo[1])
    assert asdict(again) == asdict(result)  # I8


def test_policy_change_c_tight_band(demo):
    # doc 09 §7: absolute tolerance 0.4 p. b. flips C to a 'now' alternative; partial dropped by the minimum trade
    ds = demo[0]
    pol = default_policies(ds)
    pol["Klient C"] = replace(pol["Klient C"], band_abs=D("0.4"))
    c = next(x for x in evaluate(ds, pol).clients if x.name == "Klient C")
    assert c.recommended.startswith("NOW_")  # the tight band makes C act today
    orders = next(a for a in c.alternatives if a.id == "NOW_T").orders
    assert [(o.side, o.ticker, o.units) for o in orders] == [("SELL", "VWCE", 9)]


def test_policy_change_a_to_target(demo, by_client):
    ds = demo[0]
    pol = default_policies(ds)
    pol["Klient A"] = replace(pol["Klient A"], inner_band=D(0))
    a = next(x for x in evaluate(ds, pol).clients if x.name == "Klient A")
    before = next(x for x in by_client["Klient A"].alternatives if x.id == "NOW_P")
    after = next(x for x in a.alternatives if x.id == a.recommended)
    assert a.outcome.code == "execute_now"
    assert after.turnover > before.turnover


def test_invalid_policy_blocks_only_that_client(demo):
    ds = demo[0]
    pol = default_policies(ds)
    t = dict(pol["Klient C"].targets)
    t["VWCE"] = D(45)
    pol["Klient C"] = replace(pol["Klient C"], targets=t)
    res = {c.name: c for c in evaluate(ds, pol).clients}
    assert res["Klient C"].status == "policy_error" and res["Klient C"].outcome.code == "fix_data"
    assert res["Klient A"].status == "ok"


def test_ledger_balances_never_negative_on_feasible_plans(result):
    for c in result.clients:
        for a in c.alternatives:
            if a.feasible:
                assert all(e.balance_after >= D("-0.005") for e in a.ledger), (c.name, a.id)
