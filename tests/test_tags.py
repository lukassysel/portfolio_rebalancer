"""Reason tags: every proposed order says which rule created it, with the engine's numbers."""

from decimal import Decimal as D

REASONS = {"band", "equity_band", "idle_cash", "cash_band", "to_target", "withdrawal", "cash_target", "deposit",
           "after_time_test"}


def rec(c):
    return next(a for a in c.alternatives if a.id == c.recommended)


def test_every_order_of_every_alternative_has_a_reason(result):
    for c in result.clients:
        for a in c.alternatives:
            for o in a.orders:
                assert any(t.kind == "reason" and t.code in REASONS for t in o.tags), (c.name, a.id, o)


def test_b_sells_for_the_january_withdrawal_and_the_vwce_band(result):
    b = next(c for c in result.clients if c.name == "Klient B")
    vwce = next(o for o in rec(b).orders if o.ticker == "VWCE" and o.side == "SELL")
    codes = {t.code: t.params for t in vwce.tags}
    # today's sales provide for the four withdrawals inside the 90-day reserve (rents Nov–Jan and 15 Jan)
    assert (codes["withdrawal"]["date"], codes["withdrawal"]["last"], codes["withdrawal"]["count"]) == \
           ("2026-11-01", "2027-01-15", "4") and D(codes["withdrawal"]["amount"]) == 1755000
    assert codes["band"]["measure"] == "B" and D(codes["band"]["deviation"]) > D(codes["band"]["band"])


def test_b_later_reserve_sale_names_only_the_withdrawals_it_adds(result):
    b = next(c for c in result.clients if c.name == "Klient B")
    later = [o for o in rec(b).orders if str(o.trade_date) == "2026-12-01"]
    for o in later:
        w = next(t.params for t in o.tags if t.code == "withdrawal")
        assert (w["date"], w["last"], w["count"]) == ("2027-02-01", "2027-03-01", "2")


def test_taxable_sale_carries_a_tax_warning(result):
    e = next(c for c in result.clients if c.name == "Klient E")
    now = next(a for a in e.alternatives if a.id == "NOW_P")
    warn = [t for o in now.orders for t in o.tags if t.code == "taxable_gain"]
    assert warn and D(warn[0].params["tax"]) > 0


def _e(demo):
    from dataclasses import replace
    ds = demo[0]
    e = next(c for c in ds.clients if c.name == "Klient E")
    return ds, e, replace


def test_delayed_buy_keeps_the_reason_of_the_step_that_created_it(demo):
    from datetime import date
    from rebalancer.engine import evaluate
    from rebalancer.engine.model import Flow
    ds, e, replace = _e(demo)
    e2 = replace(e, flows=list(e.flows) + [Flow(date(2026, 11, 24), D(1000), "Vklad")])
    c = evaluate(replace(ds, clients=[e2])).clients[0]
    igln = next(o for a in c.alternatives if a.id == "WAIT_TAX_P" for o in a.orders if o.ticker == "IGLN")
    codes = [t.code for t in igln.tags]
    assert "after_time_test" in codes and "deposit" not in codes


def test_no_tax_warning_when_the_year_stays_under_the_receipts_exemption(result):
    for c in result.clients:
        for a in c.alternatives:
            for o in a.orders:
                for t in o.tags:
                    if t.code == "taxable_gain":
                        assert D(t.params["tax"]) <= (a.tax or 0) + D("0.01")
