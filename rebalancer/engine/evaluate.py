"""Pure entry point ``evaluate(dataset, policies, assumptions)`` (doc 08 §§7–10).

No clock, randomness or I/O: identical inputs give identical results. Each client is evaluated in isolation;
a failure in one client never affects the others (doc 07 §8 item 8).
"""

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from typing import Callable

from .. import MODEL_VERSION
from . import calendar as cal
from .model import CASH, CZK, FO, Assumptions, Client, Dataset, Policy
from .policy import default_policy, validate_policy
from .results import (AlternativeOut, BalancePoint, Benchmark, BenchmarkTotal, CheckpointOut, ClientResult,
                      EvaluationResult, FxOut, Issue, LedgerEntry, LotSaleOut, OrderOut, OutcomeOut, RankingOut, ReserveBridge, ResidualOut,
                      StepOut, StressOut, TriggerOut, UncertaintyOut, WaitTestOut)
from . import explain as ex
from .simulation import Simulation
from .validation import validate_dataset
from .valuation import value_client

D = Decimal
ZERO = D(0)
FAR = date(9999, 12, 31)

LABELS = {
    "fix_data": "Opravit data",
    "ensure_liquidity": "Zajistit likviditu do {date}",
    "review": "Posoudit: {what}",
    "execute_now": "Provést nyní",
    "wait": "Vyčkat do {date}",
    "check": "Zkontrolovat",
    "no_action": "Bez zásahu",
}
REVIEW_TEXT = {
    "hard_constraints": "nelze splnit tvrdá omezení",
    "withdrawals_uncovered": "plánované výběry nelze pokrýt",
    "residual": "zbývající odchylky od pásem",
    "uncertain": "výsledek závisí na nejistém předpokladu",
}


def czech_date(d: date) -> str:
    return f"{d.day}. {d.month}. {d.year}"


@dataclass
class Run:
    """One simulated alternative plus its cost metrics."""

    id: str
    kind: str
    mode: str | None
    wait_date: date | None
    sim: Simulation
    feasible: bool
    violation: tuple | None
    residual: Decimal
    notes: list
    start: date
    commissions: Decimal
    fx_cost: Decimal
    tax15: Decimal | None
    tax23: Decimal | None
    tax_corp: Decimal | None
    order_count: int
    turnover: Decimal
    first: date


def _run(ds: Dataset, client: Client, pol: Policy, a: Assumptions, alt: str, kind: str, mode: str | None,
         wait_date: date | None, plan: Callable[[Simulation], None], tax_rule: str) -> Run:
    s = Simulation(ds, client, pol, a, tax_rule)
    plan(s)
    viol, start, r, notes = _finish(s)
    return Run(alt, kind, mode, wait_date, s, viol is None, viol, r, notes, start, s.commissions_czk(), s.fx_costs(),
               s.tax(a.tax_rate), s.tax(a.tax_rate_high), s.tax(a.corporate_tax_rate, corporate=True)
               if client.tax_regime != FO else None, len(s.orders),
               sum((D(o.units) * s.u(o.ticker) for o in s.orders.values()), ZERO),
               min([o.date for o in s.orders.values()] + [FAR]))


def _finish(s: Simulation):
    s.reserve_fx()
    viol = s.invariant_violation()
    start = max(s.rebal_dates) if s.rebal_dates else s.as_of
    start = max([start] + [o.date for o in s.orders.values() if o.date >= start and "reserve" not in o.purposes])
    r, notes = s.residual(start)
    return viol, start, r, notes


def _plan_now(mode: str):
    def plan(s: Simulation) -> None:
        d = s.first_trade_date
        s.rebalance(d, mode, "now")
        s.reserve_step(d, s.next_followup(d), "reserve")
        s.followups(mode, d)
    return plan


def _plan_wait(mode: str, wd: date, reason: str):
    def plan(s: Simulation) -> None:
        s.reserve_step(s.first_trade_date, wd, "reserve")
        s.rebalance(wd, mode, reason)
        s.reserve_step(wd, s.next_followup(wd), "reserve")
        s.followups(mode, wd)
    return plan


def _generate(ds, client, pol, a, tax_rule) -> dict[str, Run]:
    as_of = ds.valuation_date
    runs = {"BASE": _run(ds, client, pol, a, "BASE", "base", None, None, lambda s: None, tax_rule)}
    for m in "PT":
        runs[f"NOW_{m}"] = _run(ds, client, pol, a, f"NOW_{m}", "now", m, None, _plan_now(m), tax_rule)
    probe = runs["BASE"].sim
    deposits = [vd for vd, amt, _ in probe.flows if amt > 0 and (vd - as_of).days <= pol.max_wait_days]
    if deposits:
        wd = min(deposits)
        for m in "PT":
            runs[f"WAIT_DEP_{m}"] = _run(ds, client, pol, a, f"WAIT_DEP_{m}", "wait_deposit", m, wd,
                                         _plan_wait(m, wd, "wait_deposit"), tax_rule)
    taxable = {t.first_exempt for m in "PT" for t in runs[f"NOW_{m}"].sim.taxlots
               if not t.exempt and t.first_exempt is not None}
    waits = sorted(x for x in taxable if as_of < x and (x - as_of).days <= pol.max_wait_days)
    if waits:
        wd = waits[0]
        for m in "PT":
            runs[f"WAIT_TAX_{m}"] = _run(ds, client, pol, a, f"WAIT_TAX_{m}", "wait_tax", m, wd,
                                         _plan_wait(m, wd, "wait_tax"), tax_rule)
    return runs


@dataclass
class Choice:
    recommended: str | None
    order: list[str]
    wait_tests: dict[str, WaitTestOut]
    eligible: dict[str, bool]
    triggers_today: list


def _choose(runs: dict[str, Run], client: Client, pol: Policy, nav: Decimal,
            rank_tax: Callable[[Run], Decimal], high_tax: Callable[[Run], Decimal]) -> Choice:
    """§10.1 ranking with the §10.2 waiting test."""
    base = runs["BASE"]
    trig = base.sim.breaches(base.sim.as_of)
    total = {k: r.commissions + r.fx_cost + rank_tax(r) for k, r in runs.items()}
    total_hi = {k: r.commissions + r.fx_cost + high_tax(r) for k, r in runs.items()}
    eligible = {k: r.feasible for k, r in runs.items()}
    tests: dict[str, WaitTestOut] = {}
    if base.feasible and base.residual == 0 and not trig:
        return Choice("BASE", ["BASE"], tests, eligible, trig)
    eligible["BASE"] = False
    thr = max(pol.min_saving_czk, pol.min_saving_pct / 100 * nav)
    for k, r in runs.items():
        if r.kind.startswith("wait"):
            now = runs.get(f"NOW_{r.mode}")
            days = (r.wait_date - r.sim.as_of).days
            md = r.sim.max_dev(r.wait_date)
            ok = days <= pol.max_wait_days and md <= pol.wait_dev_cap and r.feasible
            save = save_hi = None
            if now and now.feasible:
                save = total[now.id] - total[k]
                save_hi = total_hi[now.id] - total_hi[k]
                ok = ok and save >= thr and save_hi > 0
            tests[k] = WaitTestOut(days, pol.max_wait_days, md, pol.wait_dev_cap, save, save_hi, thr, ok,
                                   now.id if now else "")
            eligible[k] = eligible[k] and ok
    cand = [k for k in runs if eligible[k]]

    def key(k):
        r = runs[k]
        return (r.residual > 0, r.residual, total[k], r.order_count, r.turnover, r.first, k)

    order = sorted(cand, key=key)
    return Choice(order[0] if order else None, order, tests, eligible, trig)


def _decisive(runs, order, rank_tax) -> RankingOut:
    if not order:
        return RankingOut(None, None, None, None, None, [])
    if len(order) == 1:
        return RankingOut(order[0], None, "only", None, None, order)
    w, r = runs[order[0]], runs[order[1]]
    tiers = [("compliance", w.residual > 0, r.residual > 0, None),
             ("residual", w.residual, r.residual, (w.residual, r.residual)),
             ("cost", w.commissions + w.fx_cost + rank_tax(w), r.commissions + r.fx_cost + rank_tax(r), None),
             ("orders", w.order_count, r.order_count, None),
             ("turnover", w.turnover, r.turnover, None),
             ("timing", w.first, r.first, None)]
    for name, a, b, _ in tiers:
        if a != b:
            vals = (D(a) if isinstance(a, (int, Decimal)) and not isinstance(a, bool) else None,
                    D(b) if isinstance(b, (int, Decimal)) and not isinstance(b, bool) else None)
            return RankingOut(order[0], order[1], name, vals[0], vals[1], order)
    return RankingOut(order[0], order[1], "id", None, None, order)


def _orders_out(s: Simulation, a: Assumptions) -> list[OrderOut]:
    out = []
    for o in sorted(s.orders.values(), key=lambda o: (o.date, o.side != "SELL", s.tickers.index(o.ticker))):
        inst = s.inst[o.ticker]
        fx = s.fx[inst.currency]
        gross = D(o.units) * inst.price
        cm = s.comm(o.ticker, o.units)
        reason = ex.step_reason(s, [o], o.date)
        step = s.steps[o.steps[0]] if o.steps and o.steps[0] < len(s.steps) else None
        lots: list[LotSaleOut] = []
        if o.side == "SELL":  # parts of one combined order taken from the same lot are shown as one line
            for t in s.taxlots:
                if t.sale_date == o.date and t.ticker == o.ticker:
                    if lots and lots[-1].acquired == t.acquired:
                        p = lots[-1]
                        lots[-1] = LotSaleOut(p.acquired, p.units + t.units, p.gain + t.gain, p.exempt, p.first_exempt, p.tax_year)
                    else:
                        lots.append(LotSaleOut(t.acquired, t.units, t.gain, t.exempt, t.first_exempt, t.year))
        out.append(OrderOut(o.date, cal.add_business_days(o.date, inst.settlement_days), o.side, o.ticker, o.units,
                            inst.price, inst.currency, gross, gross * fx, cm, cm * fx, list(o.purposes),
                            o.date > s.as_of and reason in ("deposit", "reserve"), reason, lots,
                            ex.order_tags(s, o, step, a)))
    return out


def _checkpoints_out(s: Simulation) -> list[CheckpointOut]:
    out = []
    for c in s.checkpoints(s.as_of):
        m = s.measures(c)
        if m is None:
            out.append(CheckpointOut(c, s.nav(c), s.earmark(c), None, None, None, None, None))
            continue
        a, b, cnet, nav, e = m
        out.append(CheckpointOut(c, nav, e, a, b, cnet, sum((a[k] for k in s.eq), ZERO), sum((b[k] for k in s.eq), ZERO)))
    return out


def _ledger_out(s: Simulation) -> list[LedgerEntry]:
    order = {"start": 0, "flow": 1, "sell": 2, "fx": 3, "buy": 4}
    out = []
    for c in s.ccys:
        bal = ZERO
        # within one value date, credits before debits: the invariant is checked per date (doc 08 §5)
        for l in sorted(s.legs[c], key=lambda l: (l.value, l.amount < 0, order.get(l.kind, 9), l.origin)):
            bal += l.amount
            out.append(LedgerEntry(l.value, l.origin, c, l.amount, l.kind, l.ref, bal))
    return sorted(out, key=lambda e: (e.value_date, s.ccys.index(e.currency)))


def _alt_out(r: Run, rank_tax, choice: Choice, a: Assumptions) -> AlternativeOut:
    s = r.sim
    md, mv = s.min_balance(CZK)
    td, tv = s.min_cash_total()
    viol = None
    if r.violation:
        c, d, v = r.violation
        viol = {"currency": c, "date": d.isoformat(), "amount": str(v)}
    return AlternativeOut(
        r.id, r.kind, r.mode, r.wait_date, r.feasible, viol, r.feasible and r.residual == 0, r.residual,
        [ResidualOut(c, k, lab, v) for c, k, lab, v in r.notes], r.start, _orders_out(s, a),
        [FxOut(f.executed, f.available, f.source, f.target, f.source_amount, f.delivered, f.cost_czk, f.purpose, f.ref)
         for f in sorted(s.fxlog, key=lambda f: (f.executed, f.available))],
        [StepOut(x.date, x.kind, x.reason, x.mode, x.nav, x.earmark, x.basis, x.destinations, x.shortfall)
         for x in sorted(s.steps, key=lambda x: x.date)],
        r.commissions, r.fx_cost, r.tax15, r.tax23, r.tax_corp, r.commissions + r.fx_cost + rank_tax(r),
        r.order_count, r.turnover, None if r.first == FAR else r.first, mv, md, tv, td,
        [BalancePoint(d, {c: s.proj(c, d) for c in s.ccys}) for d in s.dates() if d >= s.as_of],
        _checkpoints_out(s), _ledger_out(s), choice.wait_tests.get(r.id), choice.eligible.get(r.id, False),
        choice.order.index(r.id) + 1 if r.id in choice.order else None)


def _liquidation_value(s: Simulation, a: Assumptions) -> Decimal:
    """CZK obtainable today from all cash and the sale of every holding, after commission and FX costs."""
    total = ZERO
    for c in s.ccys:
        v = s.pos(c, s.as_of) * s.fx[c]
        total += v if c == CZK else v * (1 - a.fx_cost)
    for k in s.tickers:
        n = s.units(k, s.as_of)
        if n > 0:
            inst = s.inst[k]
            net = (n * inst.price - s.comm(k, n)) * s.fx[inst.currency]
            total += net if inst.currency == CZK else net * (1 - a.fx_cost)
    return total


def _uncovered_withdrawal(s: Simulation, a: Assumptions) -> dict | None:
    """First withdrawal that cannot be covered even by liquidating everything today; deposits count only from
    their value date (doc 08 §10.4.3)."""
    available = _liquidation_value(s, a)
    run = ZERO
    for vd, amt, fd in s.flows:
        run += amt
        if amt < 0 and available + run < 0:
            return {"date": fd, "value_date": vd, "shortfall": -(available + run), "max_available": available}
    return None


def _outcome(client, runs, choice, valuation, pol, a, ds, uncertain, l1) -> tuple[OutcomeOut, list[dict]]:
    as_of = ds.valuation_date
    rec = choice.recommended
    monitoring: list[dict] = []
    # §10.4.3: a dated simulation in which even full liquidation cannot fund the withdrawals
    uncovered = _uncovered_withdrawal(runs["BASE"].sim, a)
    if uncovered:
        return OutcomeOut("review", LABELS["review"].format(what=REVIEW_TEXT["withdrawals_uncovered"]),
                          uncovered["date"], "withdrawals_uncovered",
                          {k: (v.isoformat() if isinstance(v, date) else str(v)) for k, v in uncovered.items()}), monitoring
    liquid = _liquidation_value(runs["BASE"].sim, a)
    if rec is None:
        now = runs.get("NOW_P")
        det = {}
        if now and now.violation:
            c, d, v = now.violation
            det = {"currency": c, "date": d.isoformat(), "amount": str(v)}
        det["max_available"] = str(liquid)
        det["levers"] = "reduce_or_postpone_withdrawal,add_cash,change_policy"
        return OutcomeOut("review", LABELS["review"].format(what=REVIEW_TEXT["hard_constraints"]), None,
                          "hard_constraints", det), monitoring
    if rec == "BASE":
        for comp in valuation.components + [valuation.equity]:
            if comp.band > 0 and comp.deviation != 0 and abs(comp.deviation) >= a.monitor_band_ratio * comp.band:
                monitoring.append({"type": "near_band", "scope": comp.key, "deviation": str(comp.deviation),
                                   "band": str(comp.band), "ratio": str(a.monitor_band_ratio * 100)})
        soon = as_of + timedelta(days=a.monitor_days)
        for f in valuation.flows:
            if as_of < f.value_date <= soon:
                monitoring.append({"type": "flow_soon", "date": f.date.isoformat(), "amount": str(f.amount),
                                   "days": str(a.monitor_days)})
        for lot in valuation.lots:
            if lot.first_exempt and as_of < lot.first_exempt <= soon:
                monitoring.append({"type": "time_test_soon", "scope": lot.ticker, "date": lot.first_exempt.isoformat()})
        if monitoring:
            return OutcomeOut("check", LABELS["check"], as_of, "monitoring", {}), monitoring
        return OutcomeOut("no_action", LABELS["no_action"], None, "within_bands",
                          {"max_deviation": str(valuation.max_abs_deviation)}), monitoring
    r = runs[rec]
    if uncertain:
        return OutcomeOut("review", LABELS["review"].format(what=REVIEW_TEXT["uncertain"]), r.wait_date, "uncertain",
                          {"scenarios": uncertain, "tax_high_rate": str(a.tax_rate_high * 100),
                           "corporate_rate": str(a.corporate_tax_rate * 100)}), monitoring
    if r.residual > 0:
        return OutcomeOut("review", LABELS["review"].format(what=REVIEW_TEXT["residual"]), None, "residual",
                          {"residual": str(r.residual)}), monitoring
    if r.kind.startswith("wait"):
        return OutcomeOut("wait", LABELS["wait"].format(date=czech_date(r.wait_date)), r.wait_date, r.kind,
                          {"liquidity_today": any(o.date == as_of for o in r.sim.orders.values())}), monitoring
    if l1:
        return OutcomeOut("ensure_liquidity", LABELS["ensure_liquidity"].format(date=czech_date(l1["latest_sale"])),
                          l1["latest_sale"], "liquidity",
                          {"withdrawal_date": l1["date"].isoformat(), "shortfall": str(l1["amount"])}), monitoring
    return OutcomeOut("execute_now", LABELS["execute_now"], as_of, "triggers", {}), monitoring


def _evaluate_client(ds: Dataset, client: Client, pol: Policy, a: Assumptions) -> ClientResult:
    as_of = ds.valuation_date
    horizon_end = cal.add_months(as_of, pol.planning_months)
    valuation = value_client(ds, client, pol, a, horizon_end)
    fo = client.tax_regime == FO

    def rank_tax_default(r: Run) -> Decimal:
        return r.tax15 or ZERO

    def high_tax(r: Run) -> Decimal:
        return r.tax23 or ZERO

    runs = _generate(ds, client, pol, a, "settlement")
    choice = _choose(runs, client, pol, valuation.nav, rank_tax_default, high_tax)
    base = runs["BASE"]

    # L1: the no-trade baseline violates the cash invariant (withdrawal not covered without trades)
    l1 = None
    if base.violation:
        c, d, v = base.violation
        settle = max(i.settlement_days for i in ds.instruments)
        latest = cal.sub_business_days(cal.sub_business_days(d, a.fx_lag_days), settle)
        l1 = {"date": d, "amount": -v * ds.fx[c], "latest_sale": latest, "currency": c,
              "mandatory": (d - as_of).days <= pol.reserve_days}

    # §10.3 uncertainty gate
    unc: list[UncertaintyOut] = []
    if choice.recommended and choice.recommended != "BASE":
        scen: list[tuple[str, Choice]] = []
        if fo:
            scen.append(("tax_high", _choose(runs, client, pol, valuation.nav, high_tax, high_tax)))
            raw_runs = _generate(ds, client, pol, a, "raw")
            scen.append(("raw_time_test", _choose(raw_runs, client, pol, valuation.nav,
                                                  lambda r: r.tax15 or ZERO, high_tax)))
        else:
            scen.append(("corporate_0", choice))
            scen.append(("corporate_21", _choose(runs, client, pol, valuation.nav,
                                                 lambda r: r.tax_corp or ZERO, lambda r: r.tax_corp or ZERO)))
        for name, ch in scen:
            changed = ch.recommended != choice.recommended
            kind = runs[ch.recommended].kind if ch.recommended in runs else "none"
            unc.append(UncertaintyOut(name, ch.recommended, kind, changed))
    uncertain = [u.scenario for u in unc if u.changed]

    outcome, monitoring = _outcome(client, runs, choice, valuation, pol, a, ds, uncertain, l1)

    nav0, ear0 = base.sim.nav(as_of), base.sim.earmark(as_of)

    def excess(b) -> tuple[Decimal | None, Decimal | None]:
        if b.rule == "ALL_RESERVED":
            return None, None
        x = abs(b.deviation) - b.band
        return x, x / 100 * (nav0 if b.measure == "A" else nav0 - ear0)

    triggers: list[TriggerOut] = [TriggerOut(b.rule, b.scope, b.measure, as_of, b.deviation, b.band, None, *excess(b))
                                  for b in choice.triggers_today]
    seen = {(t.scope, t.measure) for t in triggers}
    for c, k, lab, v in base.notes:
        if c > as_of and (k, lab) not in seen:
            seen.add((k, lab))
            triggers.append(TriggerOut("T2" if k == "EQ" else ("T3" if k == CASH and pol.targets[CASH] == 0 else "T1"),
                                       k, "B" if lab != "NET" else "NET", c, v, None))
    if l1:
        triggers.append(TriggerOut("L1", CZK, "LEDGER", l1["date"], None, None, l1["amount"]))

    rank_tax = rank_tax_default
    alts = [_alt_out(r, rank_tax, choice, a) for r in runs.values()]
    bridge = None
    need, czk_cash, earmark = base.sim.earmark_parts(as_of)
    if need > 0:
        nav = base.sim.nav(as_of)
        investable = nav - earmark
        target_cash = pol.targets[CASH] / 100 * investable
        bridge = ReserveBridge(as_of + timedelta(days=pol.reserve_days), need, czk_cash,
                               earmark - min(czk_cash, need) - max(ZERO, need - czk_cash), earmark, nav, investable,
                               pol.targets[CASH], target_cash, earmark + target_cash, base.sim.cash(as_of))
    ranking = _decisive(runs, choice.order, rank_tax)
    rec_run = runs.get(choice.recommended) if choice.recommended else None
    earmark_today = base.sim.earmark(as_of)
    records = (ex.band_records(valuation, base.sim, earmark_today)
               + ex.liquidity_records(base.sim, a, pol)
               + ex.alternative_records(runs, base.sim, pol, client)
               + ex.ranking_records(choice, ranking, runs, lambda r: r.commissions + r.fx_cost + rank_tax(r))
               + ex.waiting_records(choice, a)
               + ex.sensitivity_records(unc, a)
               + ex.assumption_records(client, valuation, rec_run, a, as_of))
    summ = ex.summary(outcome, rec_run, runs, choice, valuation, l1, as_of, monitoring, pol)
    records.append(summ.reason)
    return ClientResult(client.name, client.profile, client.tax_regime, client.note, "ok", [], valuation, horizon_end,
                        pol.reserve_days, earmark_today, triggers, alts, choice.recommended,
                        ranking, unc, outcome, monitoring,
                        bridge, summ, records, _stress(valuation, alts, choice.recommended, a),
                        _benchmark(valuation, alts, choice.recommended))


def _stress(v, alts: list[AlternativeOut], recommended: str | None, a: Assumptions) -> StressOut:
    k = a.stress_equity_drop / 100
    after_pct = after_date = None
    rec = next((x for x in alts if x.id == recommended), None)
    if rec and rec.id != "BASE":
        cp = next((c for c in rec.checkpoints if c.date == rec.compliance_from), None)
        if cp and cp.equity_a is not None:
            after_pct, after_date = cp.equity_a * k, cp.date
    return StressOut(a.stress_equity_drop, v.equity.value * k, v.equity.weight * k,
                     v.equity.target / 100 * v.nav * k, v.equity.target * k, after_pct, after_date)


def _benchmark(v, alts: list[AlternativeOut], recommended: str | None) -> Benchmark | None:
    """What a spreadsheet rule on today's weights would do: any band breached → fully to target now."""
    simple = "NOW_T" if v.equity.breach or any(c.breach for c in v.components) else "BASE"
    by = {x.id: x for x in alts}
    if recommended not in by or simple not in by:
        return None
    return Benchmark(simple, by[simple].total_cost - by[recommended].total_cost)


def _benchmark_total(clients: list[ClientResult]) -> BenchmarkTotal | None:
    rows = [(c, {x.id: x for x in c.alternatives}) for c in clients if c.benchmark]
    if not rows:
        return None
    simple = [by[c.benchmark.alternative] for c, by in rows]
    rec = [by[c.recommended] for c, by in rows]
    sc, rc = sum((x.total_cost for x in simple), ZERO), sum((x.total_cost for x in rec), ZERO)
    return BenchmarkTotal(len(rows), sc, rc, sc - rc, sum(x.order_count for x in simple),
                          sum(x.order_count for x in rec))


def _error_client(client: Client, status: str, issues: list[Issue]) -> ClientResult:
    first = issues[0] if issues else None
    details = {"sheet": first.sheet if first else None, "cell": first.cell if first else None,
               "message": first.message if first else ""}
    reason = ex.Explanation("decision", "data_error", False, {k: v or "" for k, v in details.items()})
    return ClientResult(client.name, client.profile, client.tax_regime, client.note, status, issues, None, None, None,
                        None, [], [], None, None, [], OutcomeOut("fix_data", LABELS["fix_data"], None, status, details),
                        [], None, ex.Summary([], [], None, None, reason), [reason])


def _calendar_policy_issues(pol: Policy, as_of: date):
    """H_r ≥ 10 business days and H_r ≤ H_p (doc 08 §6), evaluated on the real calendar."""
    from .policy import PolicyIssue
    out = []
    end = as_of + timedelta(days=pol.reserve_days)
    bdays = sum(1 for n in range(1, pol.reserve_days + 1) if cal.is_business_day(as_of + timedelta(days=n)))
    if bdays < 10:
        out.append(PolicyIssue("reserve_days", "reserve_too_short", {"business_days": str(bdays)}))
    if end > cal.add_months(as_of, pol.planning_months):
        out.append(PolicyIssue("reserve_days", "reserve_exceeds_horizon", {}))
    return out


def default_policies(ds: Dataset) -> dict[str, Policy]:
    return {c.name: default_policy(c.targets) for c in ds.clients}


def evaluate(ds: Dataset, policies: dict[str, Policy] | None = None, assumptions: Assumptions | None = None,
             issues: list[Issue] | None = None) -> EvaluationResult:
    a = assumptions or Assumptions()
    policies = policies or {}
    issues = list(issues or [])
    tickers = [i.ticker for i in ds.instruments]
    clients: list[ClientResult] = []
    with localcontext() as ctx:
        ctx.prec = 28
        found = validate_dataset(ds)
        known = {(i.code, i.client) for i in issues}
        issues += [i for i in found if (i.code, i.client) not in known]
        global_errors = [i for i in issues if i.client is None and i.severity == "error"]
        for client in ds.clients:
            own = [i for i in issues if i.client == client.name and i.severity == "error"]
            if global_errors or own:
                clients.append(_error_client(client, "data_error", own or global_errors))
                continue
            pol = policies.get(client.name) or default_policy(client.targets)
            pissues = validate_policy(pol, tickers) + _calendar_policy_issues(pol, ds.valuation_date)
            if pissues:
                clients.append(_error_client(client, "policy_error", [
                    Issue("error", p.code, f"Neplatná strategie: {p.field}", None, None, client.name) for p in pissues]))
                continue
            try:
                clients.append(_evaluate_client(ds, client, pol, a))
            except Exception as exc:  # per-client isolation
                clients.append(_error_client(client, "data_error", [
                    Issue("error", "evaluation_failed", f"Výpočet selhal: {exc}", None, None, client.name)]))
    return EvaluationResult(MODEL_VERSION, ds.valuation_date, ds.source,
                            {k: str(v) for k, v in asdict(a).items()}, [i for i in issues if i.client is None], clients,
                            _benchmark_total(clients))
