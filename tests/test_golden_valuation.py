"""Golden valuation tests (doc 10 §1): expected values come from the independently verified dataset."""

from decimal import Decimal as D
from pathlib import Path

from rebalancer.adapters import demo_bytes

EPS = D("0.000001")


def test_bundled_workbook_is_the_published_data_file():
    # the assignment numbers are checked value by value below; only the firm name was dropped from two text cells
    assert demo_bytes() == (Path(__file__).parents[1] / "docs" / "data_zadani.xlsx").read_bytes()


def test_import_counts(demo, golden):
    ds, issues = demo
    assert [i for i in issues if i.severity == "error"] == []
    assert len(ds.instruments) == golden["counts"]["instruments"]
    assert len(ds.clients) == golden["counts"]["clients"]
    assert sum(len(c.lots) for c in ds.clients) == golden["counts"]["lots"]
    assert sum(len(c.cash) for c in ds.clients) == golden["counts"]["cash"]
    assert sum(len(c.flows) for c in ds.clients) == golden["counts"]["flows"]
    assert ds.valuation_date.isoformat() == golden["valuation_date"]
    assert {k: str(v) for k, v in ds.fx.items()} == golden["fx"]


def test_nav_cash_securities(by_client, golden):
    for name, g in golden["clients"].items():
        v = by_client[name].valuation
        assert v.nav.quantize(D("0.01")) == D(g["nav_czk"]), name
        assert v.cash_czk.quantize(D("0.01")) == D(g["cash_czk"]), name
        assert v.securities.quantize(D("0.01")) == D(g["securities_czk"]), name


def test_weights_and_deviations(by_client, golden):
    for name, g in golden["clients"].items():
        comps = {c.key: c for c in by_client[name].valuation.components}
        total = D(0)
        for key, w in g["weights_pct"].items():
            c = comps["CASH" if key == "cash" else key]
            assert abs(c.weight - D(w)) < EPS, (name, key)
            assert abs(c.deviation - D(g["deviations_pp"][key])) < EPS, (name, key)
            assert c.target == D(g["targets_pct"][key])
            total += c.weight
        assert abs(total - 100) < D("1e-20")


def test_relative_deviation_undefined_at_zero_target(by_client):
    a = {c.key: c for c in by_client["Klient A"].valuation.components}
    assert a["IGLN"].relative_deviation is None and a["CASH"].relative_deviation is None
    assert a["VWCE"].relative_deviation is not None


def test_lots(by_client, golden):
    for g in golden["lots"]:
        lots = [l for l in by_client[g["client"]].valuation.lots
                if l.ticker == g["ticker"] and l.acquired.isoformat() == g["purchase_date"]]
        assert len(lots) == 1
        l = lots[0]
        assert l.units == int(g["units"])
        assert l.market_value.quantize(D("0.01")) == D(g["market_value_czk"])
        assert l.unrealised_gain.quantize(D("0.01")) == D(g["unrealised_gain_czk"])
        assert l.holding_days == int(g["holding_days"])
        assert l.anniversary.isoformat() == g["three_year_anniversary"]


def test_cash_projection_without_trades(by_client, golden):
    for name, first in golden["first_negative_czk"].items():
        got = by_client[name].valuation.first_negative_czk
        assert (got.isoformat() if got else None) == first


def test_future_deposits_not_in_todays_cash(by_client):
    assert by_client["Klient A"].valuation.cash_czk == D("90375.00")
    assert by_client["Klient D"].valuation.cash_czk == D("4500000")
