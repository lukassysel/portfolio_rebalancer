"""Decision record (doc 08 §11): the engine's own, structured defence of every recommendation.

Every record is ``(section, code, passed, params)``; params are plain strings (decimals, ISO dates, codes). A user
interface or report turns each ``code`` into one fixed sentence template, identical for every client — no wording is
chosen or composed outside these rules.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from . import calendar as cal
from .model import CASH, FO, Assumptions, Client, Policy

ZERO = Decimal(0)


@dataclass(frozen=True)
class Explanation:
    section: str  # bands | liquidity | alternatives | ranking | waiting | sensitivity | assumptions | decision
    code: str
    passed: bool | None
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Tag:
    """Short reason attached to an order or a decision: a rule code plus its numbers.

    kind: reason (why the order exists) | info (cost or condition) | warning (check before trading)."""

    kind: str
    code: str
    params: dict[str, str] = field(default_factory=dict)


def _t(kind, code, **params) -> Tag:
    return Tag(kind, code, {k: _s(v) for k, v in params.items() if v is not None})


@dataclass(frozen=True)
class OrderBrief:
    side: str
    ticker: str
    units: int


@dataclass(frozen=True)
class StepBrief:
    date: date
    kind: str  # planned | conditional
    reason: str  # wait_tax | wait_deposit | deposit | reserve | now
    orders: list[OrderBrief]


@dataclass(frozen=True)
class Summary:
    """What to do and why, in one line — chosen by fixed rules from the evaluation."""

    today: list[OrderBrief]
    later: list[StepBrief]
    key_date: date | None
    key_date_kind: str | None  # trade | latest_sale | wait_until | review
    reason: Explanation


def _s(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return format(v, "f")
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def _x(section, code, passed=None, **params) -> Explanation:
    return Explanation(section, code, passed, {k: _s(v) for k, v in params.items()})


def band_records(valuation, base_sim, earmark: Decimal) -> list[Explanation]:
    """Every component against its band: today on total assets (A) and net of the withdrawal reserve (B)."""
    out = []
    as_of = base_sim.as_of
    m = base_sim.measures(as_of)
    for c in valuation.components + [valuation.equity]:
        scope = c.key
        if scope == CASH:
            if m is not None and earmark > 0:
                net = m[2]
                ok = abs(net - c.target) <= c.band if c.target > 0 else net <= c.band_high
                out.append(_x("bands", "band_check", ok, scope=scope, measure="NET", value=net, target=c.target,
                              low=c.band_low, high=c.band_high))
            else:
                out.append(_x("bands", "band_check", not c.breach, scope=scope, measure="A", value=c.weight,
                              target=c.target, low=c.band_low, high=c.band_high))
            continue
        out.append(_x("bands", "band_check", not c.breach, scope=scope, measure="A", value=c.weight, target=c.target,
                      low=c.band_low, high=c.band_high))
        if m is not None and earmark > 0:
            wb = sum((m[1][k] for k in base_sim.eq), ZERO) if scope == "EQ" else m[1][scope]
            out.append(_x("bands", "band_check", c.band_low <= wb <= c.band_high or (c.band == 0 and wb == c.target),
                          scope=scope, measure="B", value=wb, target=c.target, low=c.band_low, high=c.band_high))
    return out


def liquidity_records(base_sim, a: Assumptions, pol: Policy) -> list[Explanation]:
    out = []
    as_of = base_sim.as_of
    settle = base_sim.settle_max
    for vd, amt, fd in base_sim.flows:
        if amt < 0:
            covered = base_sim.proj("CZK", vd) >= 0
            latest = cal.sub_business_days(cal.sub_business_days(vd, a.fx_lag_days), settle)
            out.append(_x("liquidity", "withdrawal", covered, date=fd, value_date=vd, amount=-amt,
                          latest_sale=latest, within_reserve=(vd - as_of).days <= pol.reserve_days,
                          reserve_from=base_sim.reserve_checkpoint(vd)))
        else:
            out.append(_x("liquidity", "deposit", None, date=fd, value_date=vd, amount=amt))
    return out


def alternative_records(runs, base_sim, pol: Policy, client: Client) -> list[Explanation]:
    as_of = base_sim.as_of
    out = [_x("alternatives", "generated", None, id="BASE", because="baseline")]
    for m in "PT":
        if f"NOW_{m}" in runs:
            out.append(_x("alternatives", "generated", None, id=f"NOW_{m}", because="always"))
    deposits = [(vd, amt) for vd, amt, _ in base_sim.flows if amt > 0]
    if deposits:
        vd, amt = min(deposits)
        days = (vd - as_of).days
        if "WAIT_DEP_P" in runs:
            out.append(_x("alternatives", "generated", None, id="WAIT_DEP_P", because="deposit", date=vd, days=days))
        else:
            out.append(_x("alternatives", "skipped", None, kind="wait_deposit", because="beyond_max_wait", date=vd,
                          days=days, max_days=pol.max_wait_days))
    if client.tax_regime == FO:
        taxable = sorted({(t.first_exempt, t.ticker, t.acquired) for m in "PT" if f"NOW_{m}" in runs
                          for t in runs[f"NOW_{m}"].sim.taxlots if not t.exempt and t.first_exempt})
        for fe, ticker, acq in taxable:
            days = (fe - as_of).days
            if "WAIT_TAX_P" in runs and runs["WAIT_TAX_P"].wait_date == fe:
                out.append(_x("alternatives", "generated", None, id="WAIT_TAX_P", because="time_test", date=fe,
                              days=days, ticker=ticker, acquired=acq))
            elif days > pol.max_wait_days:
                out.append(_x("alternatives", "skipped", None, kind="wait_tax", because="beyond_max_wait", date=fe,
                              days=days, max_days=pol.max_wait_days, ticker=ticker, acquired=acq))
    for k, r in runs.items():
        out.append(_x("alternatives", "result", r.feasible and r.residual == 0, id=k, feasible=r.feasible,
                      residual=r.residual, cost=r.commissions + r.fx_cost + (r.tax15 or ZERO), orders=r.order_count,
                      violation_date=r.violation[1] if r.violation else None,
                      violation_currency=r.violation[0] if r.violation else None))
    return out


def ranking_records(choice, ranking, runs, total) -> list[Explanation]:
    out = []
    for i, k in enumerate(choice.order, 1):
        r = runs[k]
        out.append(_x("ranking", "rank", None, position=i, id=k, residual=r.residual, cost=total(r),
                      orders=r.order_count, turnover=r.turnover))
    excluded = [k for k in runs if k not in choice.order and k != "BASE"]
    for k in excluded:
        r = runs[k]
        why = "infeasible" if not r.feasible else ("wait_test" if k in choice.wait_tests else "not_eligible")
        out.append(_x("ranking", "excluded", False, id=k, because=why))
    if ranking and ranking.winner and ranking.runner_up:
        out.append(_x("ranking", "decisive", None, tier=ranking.decisive, winner=ranking.winner,
                      runner_up=ranking.runner_up, winner_value=ranking.winner_value,
                      runner_up_value=ranking.runner_up_value))
    return out


def waiting_records(choice, a: Assumptions) -> list[Explanation]:
    out = []
    for k, w in choice.wait_tests.items():
        out.append(_x("waiting", "wait_test", w.passed, id=k, days=w.days, max_days=w.max_days,
                      max_deviation=w.max_deviation, deviation_cap=w.deviation_cap, saving=w.saving,
                      saving_high_tax=w.saving_high_tax, min_saving=w.min_saving, compared_with=w.compared_with,
                      high_rate=a.tax_rate_high * 100))
    return out


def sensitivity_records(unc, a: Assumptions) -> list[Explanation]:
    rates = {"tax_high": a.tax_rate_high, "corporate_21": a.corporate_tax_rate}
    return [_x("sensitivity", "scenario", not u.changed, scenario=u.scenario, recommended=u.recommended,
               rate=rates[u.scenario] * 100 if u.scenario in rates else None) for u in unc]


def assumption_records(client: Client, valuation, rec_run, a: Assumptions, as_of: date) -> list[Explanation]:
    out = []
    if client.tax_regime != FO:
        out.append(_x("assumptions", "corporate_tax_unknown", None, rate=a.corporate_tax_rate * 100))
        return out
    if rec_run is None:
        return out
    for t in rec_run.sim.taxlots:
        if t.exempt and t.first_exempt and t.first_exempt > as_of:
            lot = next(l for l in valuation.lots if l.ticker == t.ticker and l.acquired == t.acquired)
            out.append(_x("assumptions", "time_test_date", None, ticker=t.ticker, purchase=t.acquired,
                          anniversary=lot.anniversary, acquisition=lot.assumed_acquisition, first_exempt=t.first_exempt,
                          sale=t.sale_date,
                          settlement=cal.add_business_days(t.sale_date, rec_run.sim.inst[t.ticker].settlement_days)))
    if any(not t.exempt for t in rec_run.sim.taxlots):
        out.append(_x("assumptions", "tax_rate", None, rate=a.tax_rate * 100, high=a.tax_rate_high * 100))
    return out


def order_tags(s, o, step, a: Assumptions) -> list[Tag]:
    """Why one order exists (the rule and its numbers at the step that created it), plus costs and warnings."""
    out: list[Tag] = []
    if step is not None and step.reason in ("deposit", "wait_deposit"):
        deps = [(fd, amt) for vd, amt, fd in s.flows if amt > 0 and vd == step.date]
        if deps:
            out.append(_t("reason", "deposit", date=deps[0][0], amount=sum((x[1] for x in deps), ZERO)))
    if step is not None and step.reason == "wait_tax":
        out.append(_t("reason", "after_time_test", date=step.date))
    if "rebalance" in o.purposes and step is not None:
        own = [b for b in step.breaches if b.scope == o.ticker and b.rule == "T1"]
        eq = [b for b in step.breaches if b.rule == "T2"]
        cash = [b for b in step.breaches if b.scope == CASH]
        if own:
            b = max(own, key=lambda b: (abs(b.deviation) - b.band, b.measure == "A"))
            out.append(_t("reason", "band", scope=b.scope, measure=b.measure, deviation=b.deviation, band=b.band))
        elif eq and o.ticker in s.eq:
            b = max(eq, key=lambda b: (abs(b.deviation) - b.band, b.measure == "A"))
            out.append(_t("reason", "equity_band", measure=b.measure, deviation=b.deviation, band=b.band))
        elif cash and o.side == "BUY":
            b = cash[0]
            out.append(_t("reason", "idle_cash" if b.rule == "T3" else "cash_band", deviation=b.deviation, band=b.band))
        elif step.weights:
            out.append(_t("reason", "to_target", scope=o.ticker, deviation=step.weights[o.ticker] - s.t[o.ticker]))
    if {"liquidity", "topup", "reserve"} & set(o.purposes):
        # the withdrawals this sale provides for: those its steps bring into the reserve, not covered by earlier steps
        idx = [i for i in o.steps if i < len(s.steps)]
        hi = max([s.steps[i].covers_to for i in idx if s.steps[i].covers_to] + [o.date])
        lo = max([s.steps[j].covers_to for j in range(min(idx, default=0)) if s.steps[j].covers_to] + [s.as_of])
        due = sorted((vd, amt, fd) for vd, amt, fd in s.flows if amt < 0 and lo < vd <= hi)
        if due:
            out.append(_t("reason", "withdrawal", date=due[0][2], last=due[-1][2], count=len(due),
                          amount=-sum((x[1] for x in due), ZERO)))
        else:
            out.append(_t("reason", "cash_target", target=s.t[CASH]))
    if o.side == "SELL":
        lots = [t for t in s.taxlots if t.sale_date == o.date and t.ticker == o.ticker]
        gain = sum((t.gain for t in lots if not t.exempt), ZERO)
        if s.fo and gain > 0:
            # same rules as Simulation.tax(): yearly receipts test, gains netted against losses within the year
            year = [t for t in s.taxlots if t.year == lots[0].year]
            receipts = sum((Decimal(t.units) * s.u(t.ticker) for t in year), ZERO)
            net = max(sum((t.gain for t in year if not t.exempt), ZERO), ZERO)
            tax = min(gain, net) * a.tax_rate if receipts > a.receipts_exemption else ZERO
            if tax > 0:
                out.append(_t("warning", "taxable_gain", gain=gain, tax=tax, rate=a.tax_rate * 100))
        for t in lots:
            if t.exempt and t.first_exempt and t.first_exempt > s.as_of:
                out.append(_t("warning", "verify_acquisition", ticker=t.ticker, acquired=t.acquired,
                              acquisition=cal.add_business_days(t.acquired, a.acquisition_settlement_days),
                              first_exempt=t.first_exempt))
                break
    else:
        settle = cal.add_business_days(o.date, s.inst[o.ticker].settlement_days)
        fx = [f for f in s.fxlog if f.purpose == "purchase" and f.ref == o.ticker and f.available == settle]
        if fx:
            out.append(_t("info", "fx", cost=sum((f.cost_czk for f in fx), ZERO), source=fx[0].source,
                          target=fx[0].target))
    return out


def step_reason(s, orders, d: date) -> str:
    """Orders belong to the latest rebalancing step on or before their date; pure reserve sales to the reserve step."""
    prior = [x for x in s.steps if x.kind == "rebalance" and x.date <= d]
    if all(o.purposes == ["reserve"] for o in orders) or not prior:
        return "reserve"
    return max(prior, key=lambda x: x.date).reason


def summary(outcome, rec_run, runs, choice, valuation, l1, as_of, monitoring, pol) -> Summary:
    first_trade = rec_run.sim.first_trade_date if rec_run else as_of
    today, later = [], []
    if rec_run is not None and outcome.code != "fix_data":
        orders = sorted(rec_run.sim.orders.values(), key=lambda o: (o.date, o.side != "SELL", rec_run.sim.tickers.index(o.ticker)))
        today = [OrderBrief(o.side, o.ticker, o.units) for o in orders if o.date == first_trade]
        steps: dict[date, list] = {}
        for o in orders:
            if o.date != first_trade:
                steps.setdefault(o.date, []).append(o)
        for d, os in steps.items():
            reason = step_reason(rec_run.sim, os, d)
            kind = "conditional" if reason in ("deposit", "reserve") else "planned"
            later.append(StepBrief(d, kind, reason, [OrderBrief(o.side, o.ticker, o.units) for o in os]))

    code = outcome.code
    if code == "fix_data":
        reason = _x("decision", "data_error", False, **{k: v for k, v in outcome.details.items() if v is not None})
        return Summary([], [], None, None, reason)
    if code == "no_action":
        comps = [c for c in valuation.components + [valuation.equity] if c.band > 0 or c.key == CASH]
        headroom = min(((c.band_high - c.weight) if c.key == CASH and c.target == 0 else (c.band - abs(c.deviation)))
                       for c in comps)
        reason = _x("decision", "within_bands", True, max_deviation=valuation.max_abs_deviation, min_headroom=headroom)
        return Summary([], [], cal.add_months(as_of, 1), "review", reason)
    if code == "check":
        m = monitoring[0] if monitoring else {}
        reason = _x("decision", f"monitor_{m.get('type', 'near_band')}", None, **{k: v for k, v in m.items() if k != "type"})
        return Summary([], [], cal.add_months(as_of, 1), "review", reason)
    if code == "review":
        reason = _x("decision", f"review_{outcome.reason}", False,
                    **{k: (v if isinstance(v, str) else ",".join(v) if isinstance(v, list) else v)
                       for k, v in outcome.details.items()})
        return Summary(today, later, outcome.date, None, reason)
    if code == "wait":
        w = choice.wait_tests.get(rec_run.id)
        now = runs.get(w.compared_with) if w else None
        reason = _x("decision", "wait_saves" if outcome.reason == "wait_tax" else "wait_deposit_saves", True,
                    saving=w.saving if w else None, compared_with=w.compared_with if w else None,
                    avoided_tax=now.tax15 if now else None, min_saving=w.min_saving if w else None)
        return Summary(today, later, outcome.date, "wait_until", reason)
    if code == "ensure_liquidity":
        reason = _x("decision", "liquidity_shortfall", False, withdrawal_date=l1["date"], shortfall=l1["amount"],
                    latest_sale=l1["latest_sale"])
        return Summary(today, later, l1["latest_sale"], "latest_sale", reason)
    # execute_now: the largest breach today, else the first future breach
    breaches = [b for b in choice.triggers_today if b.rule in ("T1", "T2", "T3")]
    if breaches:
        b = max(breaches, key=lambda b: (abs(b.deviation) - b.band, b.measure == "A"))
        code_ = "idle_cash" if b.rule == "T3" else "band_breach"
        reason = _x("decision", code_, False, scope=b.scope, measure=b.measure, deviation=b.deviation, band=b.band)
    else:
        note = next(iter(runs["BASE"].notes), None)
        reason = _x("decision", "future_breach", False, date=note[0] if note else None, scope=note[1] if note else None)
    return Summary(today, later, first_trade, "trade", reason)
