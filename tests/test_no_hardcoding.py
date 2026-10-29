"""Proof that recommendations come from rules + inputs, not from anything prepared for the five demo clients.

Each test changes a *fact* in the data and checks that the decision changes the way the rules say it must.
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from rebalancer.engine import evaluate
from rebalancer.engine.model import CashBalance, Client, Flow, Lot


def by_name(res):
    return {c.name: c for c in res.clients}


def test_renamed_and_reordered_clients_get_identical_results(demo, result):
    ds = demo[0]
    names = {c.name: f"Klient č. {i}" for i, c in enumerate(reversed(ds.clients), 1)}
    blind = replace(ds, clients=[replace(c, name=names[c.name], note="", profile="") for c in reversed(ds.clients)])
    got = by_name(evaluate(blind))
    for c in result.clients:
        g = got[names[c.name]]
        assert g.recommended == c.recommended and g.outcome.code == c.outcome.code
        assert [(a.id, a.total_cost, [(o.trade_date, o.side, o.ticker, o.units) for o in a.orders]) for a in g.alternatives] == \
               [(a.id, a.total_cost, [(o.trade_date, o.side, o.ticker, o.units) for o in a.orders]) for a in c.alternatives]


def test_e_no_longer_waits_when_its_lot_is_already_tax_free(demo):
    ds = demo[0]
    e = next(c for c in ds.clients if c.name == "Klient E")
    lots = [replace(l, acquired=date(2023, 6, 20)) if l.acquired == date(2023, 11, 20) else l for l in e.lots]
    res = by_name(evaluate(replace(ds, clients=[replace(e, lots=lots)])))
    assert not res["Klient E"].recommended.startswith("WAIT")  # nothing to wait for → act now


def test_b_needs_no_liquidity_step_without_the_large_withdrawal(demo):
    ds = demo[0]
    b = next(c for c in ds.clients if c.name == "Klient B")
    flows = [f for f in b.flows if f.amount != D(-1500000)]
    res = by_name(evaluate(replace(ds, clients=[replace(b, flows=flows)])))
    assert res["Klient B"].outcome.code != "ensure_liquidity"


def test_c_acts_when_a_price_moves_it_out_of_its_band(demo):
    ds = demo[0]
    instruments = [replace(i, price=i.price * D("1.4")) if i.ticker == "VWCE" else i for i in ds.instruments]
    c = next(x for x in ds.clients if x.name == "Klient C")
    res = by_name(evaluate(replace(ds, instruments=instruments, clients=[c])))
    assert res["Klient C"].outcome.code == "execute_now"
    assert any(o.side == "SELL" and o.ticker == "VWCE" for a in res["Klient C"].alternatives
               if a.id == res["Klient C"].recommended for o in a.orders)


def test_a_brand_new_client_is_evaluated_by_the_same_rules(demo):
    ds = demo[0]
    new = Client(
        name="Nový klient", profile="", tax_regime="FO",
        targets={"VWCE": D(40), "AVWS": D(10), "EUNA": D(40), "IGLN": D(5), "CASH": D(5)},
        lots=[Lot("VWCE", date(2018, 5, 2), 4000, D("60")), Lot("EUNA", date(2025, 3, 3), 20000, D("4.5"))],
        cash=[CashBalance("CZK", D(150000))],
        flows=[Flow(date(2026, 12, 20), D(-400000))],
    )
    c = evaluate(replace(ds, clients=[new])).clients[0]
    assert c.status == "ok" and c.recommended is not None
    rec = next(a for a in c.alternatives if a.id == c.recommended)
    assert rec.feasible and rec.compliant
    # VWCE is far above its 40 % target and the old lot is tax-free: the plan sells VWCE and buys the underweights
    assert any(o.side == "SELL" and o.ticker == "VWCE" for o in rec.orders)
    assert {"AVWS", "IGLN"} & {o.ticker for o in rec.orders if o.side == "BUY"}


def test_every_decision_record_has_a_ui_template(result):
    """The UI renders each engine record with one fixed template; an unknown code would surface as raw data."""
    import re
    from pathlib import Path
    src = (Path(__file__).parents[1] / "web" / "src" / "record.ts").read_text()
    templates = set(re.findall(r"^\s+([a-z_]+): \(", src, re.M))
    codes = {e.code for c in result.clients for e in c.explanations}
    codes |= {"review_residual", "review_uncertain", "review_hard_constraints", "review_withdrawals_uncovered",
              "monitor_near_band", "monitor_flow_soon", "monitor_time_test_soon", "data_error", "future_breach",
              "idle_cash", "band_breach", "wait_deposit_saves", "skipped", "excluded", "corporate_tax_unknown", "tax_rate"}
    assert codes <= templates, sorted(codes - templates)
    for c in result.clients:
        assert c.summary is not None and c.summary.reason.section == "decision"
