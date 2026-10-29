"""Current valuation on the workbook definition (doc 02, doc 08 §3): % of total NAV incl. all cash."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from . import calendar as cal
from .costs import acquisition_date, first_exempt_trade_date
from .model import CASH, CZK, FO, Assumptions, Client, Dataset, Policy
from .policy import band

D = Decimal


@dataclass(frozen=True)
class Component:
    key: str  # ticker or CASH
    value: Decimal  # CZK
    units: int | None
    weight: Decimal  # % of NAV
    target: Decimal
    deviation: Decimal  # p. b.
    relative_deviation: Decimal | None  # % of target; None when the target is 0 %
    band: Decimal
    band_low: Decimal
    band_high: Decimal
    breach: bool


@dataclass(frozen=True)
class LotView:
    ticker: str
    acquired: date
    units: int
    buy_price: Decimal
    market_value: Decimal
    cost_basis: Decimal  # CZK at valuation FX (D-TAX-3)
    unrealised_gain: Decimal
    holding_days: int
    anniversary: date
    assumed_acquisition: date | None  # D-TAX-1: purchase + settlement (credit to the owner's account)
    first_exempt: date | None  # None for legal entities (no time test)
    tax_status: str  # exempt | pending | taxable | corporate


@dataclass(frozen=True)
class CashLine:
    currency: str
    amount: Decimal
    value_czk: Decimal


@dataclass(frozen=True)
class FlowView:
    date: date
    value_date: date
    amount: Decimal
    kind: str
    note: str
    in_horizon: bool
    past: bool


@dataclass(frozen=True)
class Valuation:
    nav: Decimal
    securities: Decimal
    cash_czk: Decimal
    components: list[Component]
    equity: Component
    max_abs_deviation: Decimal
    cash: list[CashLine]
    lots: list[LotView]
    flows: list[FlowView]
    first_negative_czk: date | None  # CZK cash with scheduled flows only, no trades/FX (doc 02 §4)


def unit_value(ds: Dataset, ticker: str) -> Decimal:
    inst = next(i for i in ds.instruments if i.ticker == ticker)
    return inst.price * ds.fx[inst.currency]


def flow_value_date(flow_date: date, amount: Decimal) -> date:
    """Deposits are available from the next business day on/after; withdrawals due the last business day on/before."""
    return cal.on_or_after(flow_date) if amount > 0 else cal.on_or_before(flow_date)


def value_client(ds: Dataset, client: Client, policy: Policy, a: Assumptions, horizon_end: date) -> Valuation:
    as_of = ds.valuation_date
    units = {i.ticker: 0 for i in ds.instruments}
    for lot in client.lots:
        units[lot.ticker] += lot.units
    values = {t: D(n) * unit_value(ds, t) for t, n in units.items()}
    cash_lines = [CashLine(c.currency, c.amount, c.amount * ds.fx[c.currency]) for c in client.cash]
    cash = sum((c.value_czk for c in cash_lines), D(0))
    securities = sum(values.values(), D(0))
    nav = securities + cash

    def comp(key: str, value: Decimal, n: int | None) -> Component:
        t = policy.targets[key]
        w = value / nav * 100 if nav else D(0)
        dev = w - t
        b = band(policy, t)
        if key == CASH and t == 0:
            breach = dev > policy.idle_cash_tol
            hi = policy.idle_cash_tol
        else:
            breach = abs(dev) > b
            hi = t + b
        return Component(key, value, n, w, t, dev, (dev / t * 100) if t else None, b, max(D(0), t - b), hi, breach)

    comps = [comp(i.ticker, values[i.ticker], units[i.ticker]) for i in ds.instruments]
    comps.append(comp(CASH, cash, None))
    eq_t = sum((policy.targets[i.ticker] for i in ds.instruments if i.is_equity), D(0))
    eq_v = sum((values[i.ticker] for i in ds.instruments if i.is_equity), D(0))
    eq_w = eq_v / nav * 100 if nav else D(0)
    equity = Component("EQ", eq_v, None, eq_w, eq_t, eq_w - eq_t, None, policy.equity_band,
                       eq_t - policy.equity_band, eq_t + policy.equity_band, abs(eq_w - eq_t) > policy.equity_band)

    lots = []
    for lot in sorted(client.lots, key=lambda x: ([i.ticker for i in ds.instruments].index(x.ticker), x.acquired)):
        inst = next(i for i in ds.instruments if i.ticker == lot.ticker)
        fx = ds.fx[inst.currency]
        mv = D(lot.units) * inst.price * fx
        basis = D(lot.units) * lot.buy_price * fx
        acq = acquisition_date(lot.acquired, a) if client.tax_regime == FO else None
        if client.tax_regime == FO:
            fe = first_exempt_trade_date(lot.acquired, a)
            status = "exempt" if as_of >= fe else ("pending" if fe <= horizon_end else "taxable")
        else:
            fe, status = None, "corporate"
        lots.append(LotView(lot.ticker, lot.acquired, lot.units, lot.buy_price, mv, basis, mv - basis,
                            (as_of - lot.acquired).days, cal.add_years(lot.acquired, 3), acq, fe, status))

    flows, run, first_neg = [], sum((c.amount for c in client.cash if c.currency == CZK), D(0)), None
    for f in sorted(client.flows, key=lambda f: f.date):
        vd = flow_value_date(f.date, f.amount)
        past = vd <= as_of
        flows.append(FlowView(f.date, vd, f.amount, f.kind, f.note, as_of < vd <= horizon_end, past))
        if not past:
            run += f.amount
            if run < 0 and first_neg is None:
                first_neg = f.date

    max_dev = max(abs(c.deviation) for c in comps)
    return Valuation(nav, securities, cash, comps, equity, max_dev, cash_lines, lots, flows, first_neg)
