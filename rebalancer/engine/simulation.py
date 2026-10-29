"""Plan simulation on a value-date cash ledger (doc 08 §§5, 6, 8, 9).

One ``Simulation`` holds the *simulated* holdings of one alternative; it starts from an immutable copy of the
client's actual holdings and records the *proposed* orders. Every alternative uses the same rules; client
differences come only from the ``Policy``.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from . import calendar as cal
from .costs import commission, first_exempt_trade_date, fx_cost_czk
from .model import CASH, CZK, FO, SRO, Assumptions, Client, Dataset, Policy
from .policy import band
from .valuation import flow_value_date

D = Decimal
CENT = D("0.01")
ZERO = D(0)


@dataclass
class Leg:
    origin: date
    value: date
    amount: Decimal
    kind: str  # start | flow | sell | buy | fx
    ref: str = ""


@dataclass
class OrderRec:
    date: date
    side: str  # BUY | SELL
    ticker: str
    units: int
    purposes: list[str] = field(default_factory=list)  # rebalance | liquidity | topup | reserve
    steps: list[int] = field(default_factory=list)  # indices in Simulation.steps of the steps that sized the order


@dataclass
class FxRec:
    executed: date
    available: date
    source: str
    target: str
    source_amount: Decimal
    delivered: Decimal
    cost_czk: Decimal
    purpose: str  # withdrawal | purchase
    ref: str  # flow date or ticker


@dataclass
class TaxLotRec:
    year: int
    ticker: str
    acquired: date
    units: int
    gain: Decimal  # CZK, valuation-FX cost basis, net of the allocated sale commission
    exempt: bool
    first_exempt: date | None
    sale_date: date
    buy_price: Decimal


@dataclass
class Breach:
    rule: str  # T1 | T2 | T3
    scope: str  # ticker | EQ | CASH
    measure: str  # A | B | NET
    deviation: Decimal
    band: Decimal


@dataclass
class StepRec:
    date: date
    kind: str  # rebalance | reserve
    reason: str  # now | deposit | wait_tax | wait_deposit | reserve
    mode: str | None
    nav: Decimal
    earmark: Decimal
    basis: Decimal | None
    breaches: list[Breach]
    destinations: dict[str, Decimal] | None
    shortfall: Decimal | None
    weights: dict[str, Decimal] = field(default_factory=dict)  # pre-trade weights on total assets (A)
    covers_to: date | None = None  # withdrawals with value date up to here are provided for by this step


class Simulation:
    def __init__(self, ds: Dataset, client: Client, policy: Policy, a: Assumptions,
                 tax_rule: str = "settlement"):
        self.ds, self.client, self.pol, self.a = ds, client, policy, a
        self.as_of = ds.valuation_date
        self.plan_end = cal.add_months(self.as_of, policy.planning_months)
        self.tickers = [i.ticker for i in ds.instruments]
        self.inst = {i.ticker: i for i in ds.instruments}
        self.eq = [i.ticker for i in ds.instruments if i.is_equity]
        self.ccys = [CZK] + [c for c in ds.fx if c != CZK]
        self.fx = ds.fx
        self.fo = client.tax_regime == FO
        self.raw_tax_rule = tax_rule == "raw"
        self.t = {k: policy.targets[k] for k in self.tickers + [CASH]}
        self.b = {k: band(policy, self.t[k]) for k in self.tickers + [CASH]}
        self.lots = {k: [[l.acquired, D(l.units), l.buy_price] for l in sorted(client.lots, key=lambda x: x.acquired)
                         if l.ticker == k] for k in self.tickers}
        self.u0 = {k: sum((l[1] for l in self.lots[k]), ZERO) for k in self.tickers}
        self.legs: dict[str, list[Leg]] = {c: [] for c in self.ccys}
        for c in client.cash:
            self.legs[c.currency].append(Leg(self.as_of, self.as_of, c.amount, "start"))
        self.flows: list[tuple[date, Decimal, date]] = []  # (value date, amount, flow date)
        for f in client.flows:
            vd = flow_value_date(f.date, f.amount)
            if self.as_of < vd <= self.plan_end:
                self.flows.append((vd, f.amount, f.date))
                self.legs[CZK].append(Leg(vd, vd, f.amount, "flow", f.date.isoformat()))
        self.flows.sort()
        self.orders: dict[tuple[date, str, str], OrderRec] = {}
        self.taxlots: list[TaxLotRec] = []
        self.fxlog: list[FxRec] = []
        self.sold: set[str] = set()
        self.bought: set[str] = set()
        self.rebal_dates: list[date] = []
        self.steps: list[StepRec] = []
        self.cur_step = 0  # index the running step will get in self.steps
        self.settle_max = max(i.settlement_days for i in ds.instruments)
        self.first_trade_date = cal.on_or_after(self.as_of)  # no orders on a weekend/holiday valuation date
        # minimum cash kept in CZK whenever the plan trades (policy): max(% of NAV, fixed amount)
        self.buffer = max(policy.min_cash_pct / 100 * self.nav(self.as_of), policy.min_cash_czk)

    # ---- unit values, bands -------------------------------------------------------------------------------
    def u(self, k: str) -> Decimal:
        i = self.inst[k]
        return i.price * self.fx[i.currency]

    def comm(self, k: str, q) -> Decimal:
        return commission(q, self.inst[k].price, self.a)

    def first_exempt(self, acquired: date) -> date:
        return first_exempt_trade_date(acquired, self.a, raw=self.raw_tax_rule)

    # ---- §6 valuation timeline: trade-date holdings, cash position by origin; invariant by value date (§5) ----
    def units(self, k: str, d: date) -> Decimal:
        q = self.u0[k]
        for (od, side, kk), o in self.orders.items():
            if kk == k and od <= d:
                q += o.units if side == "BUY" else -o.units
        return q

    def pos(self, c: str, d: date) -> Decimal:
        return sum((l.amount for l in self.legs[c] if l.origin <= d), ZERO)

    def proj(self, c: str, d: date) -> Decimal:
        return sum((l.amount for l in self.legs[c] if l.value <= d), ZERO)

    def dates(self) -> list[date]:
        return sorted({l.value for ls in self.legs.values() for l in ls} | {l.origin for ls in self.legs.values() for l in ls})

    def free(self, c: str, d: date) -> Decimal:
        return min([self.proj(c, x) for x in self.dates() if x >= d] + [self.proj(c, d)])

    def cash(self, d: date) -> Decimal:
        return sum((self.pos(c, d) * self.fx[c] for c in self.ccys), ZERO)

    def nav(self, d: date) -> Decimal:
        return sum((self.units(k, d) * self.u(k) for k in self.tickers), ZERO) + self.cash(d)

    def earmark_parts(self, d: date) -> tuple[Decimal, Decimal, Decimal]:
        """(need, CZK cash position, earmark E) for withdrawals with value date in (d, d + H_r] (§6)."""
        run = need = ZERO
        horizon = d + timedelta(days=self.pol.reserve_days)
        for vd, amt, _ in self.flows:
            if d < vd <= horizon:
                run += amt
                need = max(need, -run)
        p = max(ZERO, self.pos(CZK, d))
        return need, p, min(p, need) + max(ZERO, need - p) / (1 - self.a.fx_cost)

    def earmark(self, d: date) -> Decimal:
        return self.earmark_parts(d)[2]

    def measures(self, d: date):
        nav, e = self.nav(d), self.earmark(d)
        if nav - e <= 0:
            return None
        a = {k: self.units(k, d) * self.u(k) / nav * 100 for k in self.tickers}
        b = {k: self.units(k, d) * self.u(k) / (nav - e) * 100 for k in self.tickers}
        cnet = (self.cash(d) - e) / (nav - e) * 100
        return a, b, cnet, nav, e

    def breaches(self, d: date) -> list[Breach]:
        m = self.measures(d)
        if m is None:
            return [Breach("ALL_RESERVED", CASH, "NET", ZERO, ZERO)]
        a, b, cnet, nav, e = m
        out = []
        for k in self.tickers:
            for lab, w in (("A", a), ("B", b)):
                if abs(w[k] - self.t[k]) > self.b[k]:
                    out.append(Breach("T1", k, lab, w[k] - self.t[k], self.b[k]))
        for lab, w in (("A", a), ("B", b)):
            eq = sum((w[k] - self.t[k] for k in self.eq), ZERO)
            if abs(eq) > self.pol.equity_band:
                out.append(Breach("T2", "EQ", lab, eq, self.pol.equity_band))
        if self.t[CASH] > 0 and abs(cnet - self.t[CASH]) > self.b[CASH]:
            out.append(Breach("T1", CASH, "NET", cnet - self.t[CASH], self.b[CASH]))
        if self.t[CASH] == 0 and cnet > self.pol.idle_cash_tol:
            out.append(Breach("T3", CASH, "NET", cnet, self.pol.idle_cash_tol))
        return out

    # ---- orders -------------------------------------------------------------------------------------------
    def sell(self, k: str, n: Decimal, d: date, purpose: str) -> None:
        if n <= 0:
            return
        key = (d, "SELL", k)
        ccy = self.inst[k].currency
        rec = self.orders.get(key)
        if rec is None:
            rec = self.orders[key] = OrderRec(d, "SELL", k, 0)
        if self.cur_step not in rec.steps:
            rec.steps.append(self.cur_step)
        tot = rec.units + int(n)
        rec.units = tot
        if purpose not in rec.purposes:
            rec.purposes.append(purpose)
        # one combined order per instrument and day: commission on the total (doc 08 §5)
        self.legs[ccy] = [l for l in self.legs[ccy] if not (l.kind == "sell" and l.ref == f"{d} {k}")]
        settle = cal.add_business_days(d, self.inst[k].settlement_days)
        self.legs[ccy].append(Leg(d, settle, tot * self.inst[k].price - self.comm(k, tot), "sell", f"{d} {k}"))
        self.sold.add(k)
        self._fifo(k, d, n, tot)

    def _fifo(self, k: str, d: date, n: Decimal, tot: int) -> None:
        inst = self.inst[k]
        rem = n
        settle = cal.add_business_days(d, inst.settlement_days)
        for lot in self.lots[k]:
            if rem == 0:
                break
            take = min(lot[1], rem)
            if take == 0:
                continue
            fe = self.first_exempt(lot[0]) if self.fo else None
            self.taxlots.append(TaxLotRec(settle.year, k, lot[0], int(take), ZERO, bool(fe and d >= fe), fe, d, lot[2]))
            lot[1] -= take
            rem -= take
        cm = self.comm(k, tot)
        fx = self.fx[inst.currency]
        for t in self.taxlots:
            if t.sale_date == d and t.ticker == k:
                t.gain = D(t.units) * (inst.price - t.buy_price) * fx - cm * t.units / tot * fx

    def book_fx(self, tgt: str, amt: Decimal, avail: date, purpose: str, ref: str) -> None:
        x = cal.sub_business_days(avail, self.a.fx_lag_days)
        for src in self.ccys:
            if src == tgt or amt <= 0:
                continue
            fs = self.free(src, x)
            if src == CZK and purpose == "purchase":
                fs -= self.buffer  # purchases never convert the minimum CZK cash
            if fs <= 0:
                continue
            fsrc, ftgt, c = self.fx[src], self.fx[tgt], self.a.fx_cost
            maxd = (fs * fsrc / ftgt * (1 - c)).quantize(CENT, ROUND_FLOOR)
            want = min(amt, maxd)
            src_amt = min((want * ftgt / (fsrc * (1 - c))).quantize(CENT, ROUND_CEILING), fs)
            if src_amt <= 0:
                continue
            got = (src_amt * fsrc / ftgt * (1 - c)).quantize(CENT, ROUND_FLOOR)
            tag = f"{purpose}:{ref}"
            self.legs[src].append(Leg(x, x, -src_amt, "fx", tag))
            self.legs[tgt].append(Leg(x, avail, got, "fx", tag))
            self.fxlog.append(FxRec(x, avail, src, tgt, src_amt, got, fx_cost_czk(src_amt, fsrc, self.a), purpose, ref))
            amt -= got

    def reserve_fx(self) -> None:
        """§9 step 7: just-in-time FX for withdrawals, (re)booked before purchase budgets are computed."""
        for c in self.ccys:
            self.legs[c] = [l for l in self.legs[c] if not (l.kind == "fx" and l.ref.startswith("withdrawal:"))]
        self.fxlog = [f for f in self.fxlog if f.purpose != "withdrawal"]
        keep = self.buffer if self.orders else ZERO  # a plan that trades keeps the minimum cash in CZK
        for vd, amt, fd in self.flows:
            if amt < 0 and self.proj(CZK, vd) < keep:
                self.book_fx(CZK, keep - self.proj(CZK, vd), vd, "withdrawal", fd.isoformat())

    def _fundable(self, k: str, p: date) -> Decimal:
        """Trade-currency cash that can fund a purchase traded on p: own free cash at settlement plus other
        currencies convertible by then (after the FX cost)."""
        inst = self.inst[k]
        ccy = inst.currency
        sd = cal.add_business_days(p, inst.settlement_days)
        own = max(ZERO, self.free(ccy, sd) - (self.buffer if ccy == CZK else ZERO))
        other = sum((max(ZERO, self.free(s, cal.sub_business_days(sd, self.a.fx_lag_days))
                         - (self.buffer if s == CZK else ZERO)) * self.fx[s]
                     / self.fx[ccy] * (1 - self.a.fx_cost) for s in self.ccys if s != ccy), ZERO)
        return own + other

    def _max_units(self, k: str, q: Decimal, budget: Decimal) -> Decimal:
        """Largest n ≤ q with n × price + commission(n) ≤ budget (closed form, then at most a few corrections)."""
        price = self.inst[k].price
        n = min(q, max(ZERO, (budget / (price * (1 + self.a.commission_rate))).to_integral_value(ROUND_FLOOR)))
        while n > 0 and n * price + self.comm(k, n) > budget:
            n = min(n - 1, max(ZERO, ((budget - self.comm(k, n)) / price).to_integral_value(ROUND_FLOOR)))
        return n

    def buy(self, k: str, q: Decimal, d: date, purpose: str) -> Decimal:
        """§5/§9.8: earliest business day (≤ 3 bd later) whose settlement can fund q units in full; if none can,
        q is reduced (equivalent to one unit at a time, computed directly). Returns the units bought."""
        inst = self.inst[k]
        ccy = inst.currency
        dates = [cal.add_business_days(d, sh) for sh in range(4)]
        budgets = [self._fundable(k, p) for p in dates]
        best = max((self._max_units(k, q, b) for b in budgets), default=ZERO)
        if best <= 0:
            return ZERO
        for p, b in zip(dates, budgets):
            if best * inst.price + self.comm(k, best) <= b:
                sd = cal.add_business_days(p, inst.settlement_days)
                self.orders[(p, "BUY", k)] = OrderRec(p, "BUY", k, int(best), [purpose], [self.cur_step])
                self.legs[ccy].append(Leg(p, sd, -(best * inst.price + self.comm(k, best)), "buy", f"{p} {k}"))
                if self.free(ccy, sd) < 0:
                    self.book_fx(ccy, -self.free(ccy, sd), sd, "purchase", k)
                self.bought.add(k)
                return best
        return ZERO

    # ---- §9 step 6 / §8 liquidity rule ---------------------------------------------------------------------
    def liquidity(self, s: Decimal, d: date, n_basis: Decimal, purpose: str, single: bool = False) -> None:
        if s <= 0:
            return
        g = s / (1 - self.a.commission_rate)
        held = [k for k in self.tickers if k not in self.bought and self.units(k, d) > 0]
        if not held:
            return
        order = self.tickers.index
        dev = {k: self.units(k, d) * self.u(k) / n_basis * 100 - self.t[k] for k in held}
        x = {k: ZERO for k in held}
        top = max(held, key=lambda k: (dev[k], -order(k)))
        if single and dev[top] / 100 * n_basis >= g:
            x[top] = g
        else:
            rem = g
            while rem > 0:
                pos_ = sorted([k for k in held if dev[k] > 0], key=lambda k: (-dev[k], order(k)))
                if not pos_:
                    tot = sum((self.units(k, d) * self.u(k) for k in held), ZERO)
                    for k in held:
                        x[k] += rem * self.units(k, d) * self.u(k) / tot
                    break
                hi = dev[pos_[0]]
                grp = [k for k in pos_ if dev[k] == hi]
                nxt = max([dev[k] for k in pos_ if dev[k] < hi] + [ZERO])
                take = min((hi - nxt) / 100 * n_basis * len(grp), rem)
                for k in grp:
                    x[k] += take / len(grp)
                    dev[k] -= take / len(grp) / n_basis * 100
                rem -= take
            small = [k for k in x if 0 < x[k] < self.pol.min_trade]
            if small:  # allocations below the minimum trade move to the largest allocation (§9.6)
                b = max((k for k in x if x[k] > 0), key=lambda k: (x[k], -order(k)))
                for k in small:
                    if k != b:
                        x[b] += x[k]
                        x[k] = ZERO
        for k in self.tickers:
            if x.get(k, ZERO) > 0:
                n = min((x[k] / self.u(k)).to_integral_value(ROUND_CEILING), self.units(k, d))
                self.sell(k, n, d, purpose)

    # ---- §9 rebalancing step ------------------------------------------------------------------------------
    def rebalance(self, d: date, mode: str, reason: str) -> None:
        self.rebal_dates.append(d)
        self.cur_step = len(self.steps)
        m = self.measures(d)
        if m is None:
            self.steps.append(StepRec(d, "rebalance", reason, mode, self.nav(d), self.earmark(d), None,
                                      self.breaches(d), None, None))
            return
        A, B, cnet, nav, E = m
        dep = sum((amt for vd, amt, _ in self.flows if amt > 0 and d < vd <= self.plan_end), ZERO)
        n_basis = nav - E + dep  # step 1, fixed for the whole step
        br = self.breaches(d)
        K = {x.scope for x in br if x.rule == "T1" and x.scope in self.tickers}
        cash_k = any(x.scope == CASH and x.rule == "T1" for x in br)
        t3 = any(x.rule == "T3" for x in br)
        eq_k = any(x.rule == "T2" for x in br)
        V = {k: self.units(k, d) * self.u(k) for k in self.tickers}
        C = self.cash(d)
        inner = self.pol.inner_band / 100
        Dk: dict[str, Decimal] = {}
        for k in self.tickers:  # step 3
            if mode == "T":
                Dk[k] = self.t[k] / 100 * n_basis
            elif k in K:
                s = 1 if B[k] > self.t[k] else -1
                Dk[k] = (self.t[k] + s * inner * self.b[k]) / 100 * n_basis
            else:
                Dk[k] = V[k]
        if mode == "T":
            Dc = E + self.t[CASH] / 100 * n_basis
        elif cash_k and self.t[CASH] > 0:
            s = 1 if cnet > self.t[CASH] else -1
            Dc = E + (self.t[CASH] + s * inner * self.b[CASH]) / 100 * n_basis
        elif t3:
            Dc = E
        else:
            Dc = max(C, E)
        Dc = max(Dc, E + self.buffer)  # a trading step keeps the minimum cash
        if mode == "P" and eq_k and self.eq:
            s = 1 if sum((B[k] - self.t[k] for k in self.eq), ZERO) > 0 else -1
            a_star = (sum((self.t[k] for k in self.eq), ZERO) + s * inner * self.pol.equity_band) / 100 * n_basis
            exc = s * (sum((Dk[k] for k in self.eq), ZERO) - a_star)
            if exc > 0:
                movers = sorted([k for k in self.eq if k in K],
                                key=lambda k: (-abs(B[k] - self.t[k]), self.tickers.index(k)))
                if movers:
                    for k in movers:
                        take = min(exc, Dk[k]) if s > 0 else exc
                        Dk[k] -= s * take
                        exc -= take
                        if exc <= 0:
                            break
                else:
                    tot = sum((Dk[k] for k in self.eq), ZERO)
                    for k in self.eq:
                        Dk[k] *= a_star / tot
        if dep > 0:  # step 4: dual cap
            for k in K:
                if V[k] > Dk[k]:
                    cap = (self.t[k] + self.b[k]) / 100 * nav - self.u(k)
                    if Dk[k] > cap:
                        Dk[k] = cap
        for k in self.tickers:  # step 5: sells
            if k not in self.bought and V[k] > Dk[k]:
                q = min(self.units(k, d), ((V[k] - Dk[k]) / self.u(k)).to_integral_value(ROUND_CEILING))
                if q * self.u(k) >= self.pol.min_trade:
                    self.sell(k, q, d, "rebalance")
        shortfall = Dc - self.cash(d)  # step 6: funding
        if shortfall > 0:
            self.liquidity(shortfall, d, n_basis, "liquidity")
            while self.cash(d) < Dc:
                held = [k for k in self.tickers if k not in self.bought and self.units(k, d) > 0]
                if not held:
                    break
                k = max(held, key=lambda k: (self.units(k, d) * self.u(k) / n_basis - self.t[k] / 100,
                                             -self.tickers.index(k)))
                # one unit at a time in the contract; for very cheap units jump close to the gap first
                gap = Dc - self.cash(d)
                est = (gap / (self.u(k) * (1 - self.a.commission_rate))).to_integral_value(ROUND_FLOOR)
                step = est - 1 if est > 1000 else D(1)
                self.sell(k, min(step, self.units(k, d)), d, "topup")
        self.reserve_fx()  # step 7
        cands = {k: Dk[k] - V[k] for k in self.tickers if k not in self.sold and self.t[k] > 0 and Dk[k] > V[k]}
        if cands:  # step 8: purchases
            sd = cal.add_business_days(d, self.settle_max)
            budget = min(self.cash(d) - Dc,
                         sum((max(ZERO, self.free(c, sd)) * self.fx[c] for c in self.ccys), ZERO) - self.buffer)
            gaps = dict(cands)
            if mode == "P" and budget > sum(gaps.values(), ZERO):
                for k in gaps:
                    gaps[k] = max(gaps[k], self.t[k] / 100 * n_basis - V[k])
            dev = {k: A[k] - self.t[k] for k in gaps}
            alloc = {k: ZERO for k in gaps}
            rem = max(ZERO, budget)
            while rem > CENT:
                open_ = [k for k in gaps if alloc[k] < gaps[k]]
                if not open_:
                    break
                lo = min(dev[k] for k in open_)
                grp = [k for k in open_ if dev[k] == lo]
                nxt = min([dev[k] for k in open_ if dev[k] > lo] + [D(10) ** 6])
                step = min((nxt - lo) / 100 * nav * len(grp), rem, min(gaps[k] - alloc[k] for k in grp) * len(grp))
                for k in grp:
                    alloc[k] += step / len(grp)
                    dev[k] += step / len(grp) / nav * 100
                rem -= step
            for k in sorted(alloc, key=lambda k: (A[k] - self.t[k], self.tickers.index(k))):
                fx = self.fx[self.inst[k].currency]
                q = (alloc[k] / (self.u(k) * (1 + self.a.commission_rate))).to_integral_value(ROUND_FLOOR)
                if q > 0 and q * self.u(k) + self.comm(k, q) * fx > alloc[k]:
                    # largest q with q·u + commission(q)·fx ≤ allocation (closed form, then exact re-check)
                    q = self._max_units(k, q, alloc[k] / fx)
                    while q > 0 and q * self.u(k) + self.comm(k, q) * fx > alloc[k]:
                        q -= 1
                if q * self.u(k) < self.pol.min_trade:
                    continue
                if q > 0:
                    self.buy(k, q, d, "rebalance")
            self.reserve_fx()
        self.steps.append(StepRec(d, "rebalance", reason, mode, nav, E, n_basis, br,
                                  {**Dk, CASH: Dc}, shortfall if shortfall > 0 else None, A,
                                  d + timedelta(days=self.pol.reserve_days)))

    # ---- §8 follow-up (2): rolling reserve ------------------------------------------------------------------
    def reserve_step(self, d: date, until: date, reason: str) -> None:
        ft = (self.t[CASH] - self.b[CASH]) / 100 if self.t[CASH] > 0 else ZERO
        tr = self.t[CASH] / 100
        cps = sorted({d} | {vd for vd, *_ in self.flows if d <= vd < until} | {x for x in self.dates() if d <= x < until})
        trig = rest = ZERO
        for c in cps:
            e = self.earmark(c)
            nav = self.nav(c)
            h = sum((self.pos(cc, c) * self.fx[cc] * (1 if cc == CZK else 1 - self.a.fx_cost) for cc in self.ccys), ZERO)
            trig = max(trig, e + ft * (nav - e) - h)
            rest = max(rest, e + tr * (nav - e) - h)
        if trig > 0:
            self.cur_step = len(self.steps)
            s = max(rest + self.buffer, self.pol.min_trade)
            n_basis = self.nav(d) - self.earmark(d)
            if n_basis <= 0:
                n_basis = self.nav(d)
            self.liquidity(s, d, n_basis, "reserve", single=True)
            self.reserve_fx()
            self.steps.append(StepRec(d, "reserve", reason, None, self.nav(d), self.earmark(d), n_basis, [], None, s,
                                      covers_to=max(cps) + timedelta(days=self.pol.reserve_days)))

    # ---- follow-up scheduling -----------------------------------------------------------------------------
    def reserve_checkpoint(self, vd: date) -> date:
        return cal.on_or_after(vd - timedelta(days=self.pol.reserve_days))

    def next_followup(self, after: date) -> date:
        ds = [vd for vd, amt, _ in self.flows if amt > 0 and vd > after]
        ds += [self.reserve_checkpoint(vd) for vd, amt, _ in self.flows if amt < 0]
        ds = [x for x in ds if x > after]
        return min(ds) if ds else self.plan_end + timedelta(days=1)

    def followups(self, mode: str, after: date) -> None:
        ev = [(vd, "dep", fd) for vd, amt, fd in self.flows if amt > 0 and vd > after]
        ev += [(self.reserve_checkpoint(vd), "res", fd) for vd, amt, fd in self.flows if amt < 0]
        for d, kind, fd in sorted(e for e in ev if e[0] > after):
            if kind == "dep":
                self.rebalance(d, mode, "deposit")
            self.reserve_step(d, self.next_followup(d), "reserve")

    # ---- §10.1 compliance and residual ------------------------------------------------------------------------
    def checkpoints(self, start: date) -> list[date]:
        c = {start, self.plan_end} | {vd for vd, *_ in self.flows if vd >= start}
        c |= {self.reserve_checkpoint(vd) for vd, amt, _ in self.flows if amt < 0}
        c |= {o for (o, *_rest) in self.orders}
        c |= {f.executed for f in self.fxlog}
        return sorted(x for x in c if x >= start)

    def residual(self, start: date):
        worst, notes = ZERO, []
        for c in self.checkpoints(start):
            m = self.measures(c)
            if m is None:
                notes.append((c, "ALL", "NET", ZERO))
                worst = max(worst, D(100))
                continue
            A, B, cnet, nav, E = m
            r = ZERO
            for k in self.tickers:
                for lab, w, base in (("A", A, nav), ("B", B, nav - E)):
                    x = abs(w[k] - self.t[k]) - self.b[k] - self.u(k) / base * 100
                    if x > 0:
                        r += x
                        notes.append((c, k, lab, w[k] - self.t[k]))
            if self.eq:
                for lab, w, base in (("A", A, nav), ("B", B, nav - E)):
                    x = abs(sum((w[k] - self.t[k] for k in self.eq), ZERO)) - self.pol.equity_band \
                        - min(self.u(k) for k in self.eq) / base * 100
                    if x > 0:
                        r += x
                        notes.append((c, "EQ", lab, sum((w[k] - self.t[k] for k in self.eq), ZERO)))
            if self.t[CASH] > 0:
                x = abs(cnet - self.t[CASH]) - self.b[CASH]
            else:
                x = cnet - self.pol.idle_cash_tol
            if x > 0:
                r += x
                notes.append((c, CASH, "NET", cnet - self.t[CASH]))
            worst = max(worst, r)
        return worst, notes

    def max_dev(self, upto: date) -> Decimal:
        m = ZERO
        for c in [x for x in self.checkpoints(self.as_of) if x < upto]:
            ms = self.measures(c)
            if ms is None:
                continue
            A, B, *_ = ms
            for w in (A, B):
                m = max([m] + [abs(w[k] - self.t[k]) for k in self.tickers]
                        + ([abs(sum((w[k] - self.t[k] for k in self.eq), ZERO))] if self.eq else []))
        return m

    def invariant_violation(self):
        """First (currency, date, balance) where the projected settled balance is negative (§5)."""
        for d in self.dates():
            for c in self.ccys:
                v = self.proj(c, d)
                if v < D("-0.005"):
                    return c, d, v
        return None

    def min_cash_total(self):
        """Lowest settled cash over all currencies, in CZK, and its date."""
        pts = [(d, self.cash(d)) for d in self.dates() if d >= self.as_of]  # positions: FX in transit counts
        if not pts:
            return self.as_of, self.cash(self.as_of)
        return min(pts, key=lambda x: (x[1], x[0]))

    def min_balance(self, c: str):
        pts = [(d, self.proj(c, d)) for d in self.dates() if d >= self.as_of]
        if not pts:
            return self.as_of, ZERO
        d, v = min(pts, key=lambda x: (x[1], x[0]))
        return d, v

    def tax(self, rate: Decimal, corporate: bool = False) -> Decimal | None:
        """FO: annual §10 pool of non-exempt sales, floor 0, 100 000 Kč receipts test (D-TAX-4).
        s.r.o.: not determinable (None) unless ``corporate`` — then rate × realised economic gain (D-TAX-5)."""
        if not self.fo:
            if not self.taxlots:
                return ZERO  # nothing sold: no tax, whatever the book values
            if not corporate:
                return None
            total = ZERO
            for y in {t.year for t in self.taxlots}:
                total += max(sum((t.gain for t in self.taxlots if t.year == y), ZERO), ZERO) * rate
            return total
        total = ZERO
        for y in {t.year for t in self.taxlots}:
            rows = [t for t in self.taxlots if t.year == y]
            if sum((D(t.units) * self.u(t.ticker) for t in rows), ZERO) <= self.a.receipts_exemption:
                continue
            total += max(sum((t.gain for t in rows if not t.exempt), ZERO), ZERO) * rate
        return total

    def commissions_czk(self) -> Decimal:
        return sum((self.comm(o.ticker, o.units) * self.fx[self.inst[o.ticker].currency]
                    for o in self.orders.values()), ZERO)

    def fx_costs(self) -> Decimal:
        return sum((f.cost_czk for f in self.fxlog), ZERO)


__all__ = ["Simulation", "SRO"]
