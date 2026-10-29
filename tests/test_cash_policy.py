"""Minimum cash kept when the plan trades."""

from dataclasses import replace
from decimal import Decimal as D

from rebalancer.engine import evaluate
from rebalancer.engine.policy import default_policy


def rec(c):
    return next(a for a in c.alternatives if a.id == c.recommended)


def test_czk_cash_never_drops_below_the_buffer_after_trading(result):
    for name in ("Klient B", "Klient E"):
        c = next(x for x in result.clients if x.name == name)
        a = rec(c)
        buffer = max(D("0.005") * c.valuation.nav, D(10000))
        first_out = min(f.value_date for f in c.valuation.flows if f.amount < 0 and not f.past)
        after = [p.balances["CZK"] for p in a.balances if p.date >= first_out]
        assert min(after) >= buffer - D("0.01"), name


def test_settings_off_restore_the_contract_behaviour(demo):
    ds = demo[0]
    b = next(c for c in ds.clients if c.name == "Klient B")
    pol = replace(default_policy(b.targets), min_cash_pct=D(0), min_cash_czk=D(0))
    c = evaluate(replace(ds, clients=[b]), {b.name: pol}).clients[0]
    assert rec(c).min_czk < 1  # without a buffer the CZK account is run down to the last haléř (0,23 Kč)
