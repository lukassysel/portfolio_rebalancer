"""Property tests (doc 10 §1, §3): invariants I1–I8 on randomly generated small portfolios."""

from datetime import date, timedelta
from decimal import Decimal as D

from hypothesis import HealthCheck, given, settings, strategies as st

from rebalancer.engine import evaluate
from rebalancer.engine.model import CashBalance, Client, Dataset, Flow, Instrument, Lot

AS_OF = date(2026, 10, 23)
INSTRUMENTS = [
    Instrument("VWCE", "", "", "EUR", "Akcie (globální)", D("142.5")),
    Instrument("AVWS", "", "", "EUR", "Akcie (small cap value)", D("12.6")),
    Instrument("EUNA", "", "", "EUR", "Dluhopisy", D("4.62")),
    Instrument("IGLN", "", "", "USD", "Zlato", D("78.4")),
]
FX = {"CZK": D(1), "EUR": D("24.3"), "USD": D(21)}
TICKERS = [i.ticker for i in INSTRUMENTS]


@st.composite
def targets(draw):
    cuts = sorted(draw(st.lists(st.integers(0, 100), min_size=4, max_size=4)))
    parts = [b - a for a, b in zip([0] + cuts, cuts + [100])]
    return {k: D(v) for k, v in zip(TICKERS + ["CASH"], parts)}


@st.composite
def clients(draw):
    lots = []
    for k in TICKERS:
        for _ in range(draw(st.integers(0, 2))):
            lots.append(Lot(k, AS_OF - timedelta(days=draw(st.integers(1, 3000))), draw(st.integers(1, 20000)),
                            D(draw(st.integers(1, 200))) / 10 if k != "VWCE" else D(draw(st.integers(500, 1500))) / 10))
    cash = [CashBalance("CZK", D(draw(st.integers(0, 3_000_000))))]
    if draw(st.booleans()):
        cash.append(CashBalance("EUR", D(draw(st.integers(0, 20000)))))
    flows = []
    for _ in range(draw(st.integers(0, 3))):
        amt = D(draw(st.integers(-800_000, 800_000)))
        if amt != 0:
            flows.append(Flow(AS_OF + timedelta(days=draw(st.integers(1, 200))), amt))
    regime = draw(st.sampled_from(["FO", "s.r.o."]))
    return Client("P", "", regime, draw(targets()), "", lots, cash, flows)


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(clients())
def test_invariants_hold_for_random_portfolios(client):
    ds = Dataset(AS_OF, INSTRUMENTS, FX, [client])
    res = evaluate(ds)
    c = res.clients[0]
    assert c.status == "ok", c.issues
    assert c.outcome.code in {"ensure_liquidity", "review", "execute_now", "wait", "check", "no_action"}
    held0 = {k: sum(l.units for l in client.lots if l.ticker == k) for k in TICKERS}
    for a in c.alternatives:
        held = dict(held0)
        bought, sold, keys = set(), set(), set()
        for o in a.orders:
            assert isinstance(o.units, int) and o.units > 0  # I1, I10
            assert (o.trade_date, o.side, o.ticker) not in keys  # one order per instrument and day
            keys.add((o.trade_date, o.side, o.ticker))
            assert o.trade_date.weekday() < 5  # business days only
            assert any(t.kind == "reason" for t in o.tags)  # every order names the rule that created it
            held[o.ticker] += o.units if o.side == "BUY" else -o.units
            assert held[o.ticker] >= 0  # no short sales
            (bought if o.side == "BUY" else sold).add(o.ticker)
            if o.side == "BUY":
                assert client.targets[o.ticker] > 0  # I6
            else:
                assert sum(l.units for l in o.lots) == o.units  # I3 FIFO consumption
        assert not (bought & sold)  # I7 no round trips
        if a.feasible:  # I2 settled cash never negative
            assert all(v >= D("-0.005") for p in a.balances for v in p.balances.values())
        assert a.total_cost >= 0
    if c.recommended and c.recommended != "BASE":
        rec = next(a for a in c.alternatives if a.id == c.recommended)
        assert rec.feasible
    again = evaluate(ds)  # I8 determinism
    assert again == res
