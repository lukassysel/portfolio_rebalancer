"""Engine output types (JSON-serialisable via the API layer: Decimal → string, date → ISO)."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .explain import Explanation, Summary, Tag
from .valuation import Valuation


@dataclass(frozen=True)
class Issue:
    """Validation issue with a sheet/cell reference (doc 08 §12)."""

    severity: str  # error | warning
    code: str
    message: str  # Czech text
    sheet: str | None = None
    cell: str | None = None
    client: str | None = None


@dataclass(frozen=True)
class TriggerOut:
    rule: str  # T1 | T2 | T3 | L1 | ALL_RESERVED
    scope: str
    measure: str  # A | B | NET | LEDGER
    date: date
    deviation: Decimal | None
    band: Decimal | None
    amount: Decimal | None = None  # L1: shortfall in CZK
    excess: Decimal | None = None  # today's breaches: p. b. beyond the band edge (|deviation| − band)
    excess_czk: Decimal | None = None  # the same on the measure's basis (A: NAV, B/NET: NAV − reserve), in CZK


@dataclass(frozen=True)
class LotSaleOut:
    acquired: date
    units: int
    gain: Decimal
    exempt: bool
    first_exempt: date | None
    tax_year: int


@dataclass(frozen=True)
class OrderOut:
    trade_date: date
    settlement_date: date
    side: str  # BUY | SELL
    ticker: str
    units: int
    price: Decimal
    currency: str
    gross: Decimal  # trade currency
    gross_czk: Decimal
    commission: Decimal  # trade currency
    commission_czk: Decimal
    purposes: list[str]
    conditional: bool  # follow-up step triggered by a later event (deposit, reserve top-up)
    step_reason: str  # now | deposit | reserve | wait_tax | wait_deposit
    lots: list[LotSaleOut] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)  # why this order exists, its costs and warnings


@dataclass(frozen=True)
class FxOut:
    executed: date
    available: date
    source: str
    target: str
    source_amount: Decimal
    delivered: Decimal
    cost_czk: Decimal
    purpose: str
    ref: str


@dataclass(frozen=True)
class StepOut:
    date: date
    kind: str
    reason: str
    mode: str | None
    nav: Decimal
    earmark: Decimal
    basis: Decimal | None
    destinations: dict[str, Decimal] | None
    amount: Decimal | None


@dataclass(frozen=True)
class BalancePoint:
    date: date
    balances: dict[str, Decimal]  # projected settled balance per currency (value dates)


@dataclass(frozen=True)
class LedgerEntry:
    """One value-dated cash movement and the settled balance of its currency after it (doc 08 §5)."""

    value_date: date
    origin: date
    currency: str
    amount: Decimal
    kind: str  # start | flow | sell | buy | fx
    ref: str
    balance_after: Decimal


@dataclass(frozen=True)
class CheckpointOut:
    date: date
    nav: Decimal
    earmark: Decimal
    weights_a: dict[str, Decimal] | None
    weights_b: dict[str, Decimal] | None
    cash_net: Decimal | None
    equity_a: Decimal | None
    equity_b: Decimal | None


@dataclass(frozen=True)
class ResidualOut:
    date: date
    scope: str
    measure: str
    deviation: Decimal


@dataclass(frozen=True)
class WaitTestOut:
    days: int
    max_days: int
    max_deviation: Decimal
    deviation_cap: Decimal
    saving: Decimal | None
    saving_high_tax: Decimal | None
    min_saving: Decimal
    passed: bool
    compared_with: str


@dataclass(frozen=True)
class AlternativeOut:
    id: str  # BASE | NOW_P | NOW_T | WAIT_DEP_P | WAIT_DEP_T | WAIT_TAX_P | WAIT_TAX_T
    kind: str  # base | now | wait_deposit | wait_tax
    mode: str | None  # P | T
    wait_date: date | None
    feasible: bool
    infeasibility: dict | None  # {currency, date, amount}
    compliant: bool
    residual: Decimal
    residual_notes: list[ResidualOut]
    compliance_from: date
    orders: list[OrderOut]
    fx: list[FxOut]
    steps: list[StepOut]
    commissions: Decimal
    fx_cost: Decimal
    tax: Decimal | None  # at the model rate (15 %); None = not determinable (s.r.o.)
    tax_high: Decimal | None  # 23 % sensitivity
    tax_corporate: Decimal | None  # s.r.o.: conditional 21 % × realised economic gain
    total_cost: Decimal
    order_count: int
    turnover: Decimal
    first_order: date | None
    min_czk: Decimal
    min_czk_date: date
    min_cash: Decimal  # lowest settled cash over all currencies, in CZK
    min_cash_date: date
    balances: list[BalancePoint]
    checkpoints: list[CheckpointOut]
    ledger: list[LedgerEntry]
    wait_test: WaitTestOut | None = None
    eligible: bool = True
    rank: int | None = None


@dataclass(frozen=True)
class RankingOut:
    winner: str | None
    runner_up: str | None
    decisive: str | None  # feasible | compliance | residual | cost | orders | turnover | timing | id
    winner_value: Decimal | None
    runner_up_value: Decimal | None
    order: list[str]


@dataclass(frozen=True)
class UncertaintyOut:
    scenario: str  # tax_high | raw_time_test | corporate_0 | corporate_21
    recommended: str | None
    outcome: str
    changed: bool


@dataclass(frozen=True)
class OutcomeOut:
    code: str  # fix_data | ensure_liquidity | review | execute_now | wait | check | no_action
    label: str  # Czech label
    date: date | None
    reason: str  # reason key for the UI
    details: dict


@dataclass(frozen=True)
class ReserveBridge:
    """How today's cash requirement is built (doc 09 §3 „reserve bridge“), all values from the engine."""

    window_end: date
    withdrawals: Decimal  # maximum cumulative net outflow within the reserve horizon
    czk_cash: Decimal
    fx_allowance: Decimal  # extra cost of converting foreign cash/proceeds for the uncovered part
    earmark: Decimal
    nav: Decimal
    investable: Decimal  # NAV − earmark
    cash_target_pct: Decimal
    target_cash: Decimal  # cash target × investable
    required_cash: Decimal  # earmark + target cash
    cash_today: Decimal


@dataclass(frozen=True)
class StressOut:
    """Illustrative equity drawdown: loss in CZK and % of NAV today, at the target allocation and after the plan."""

    drop: Decimal  # % fall of all equity ETFs, everything else unchanged
    loss: Decimal
    loss_pct: Decimal
    target_loss: Decimal
    target_pct: Decimal
    after_pct: Decimal | None  # after the recommended plan (equity weight at its completion checkpoint)
    after_date: date | None


@dataclass(frozen=True)
class Benchmark:
    """The simple rule: when a band (on today's total-asset weights) is breached, rebalance fully to target now;
    otherwise do nothing. Compared with the recommendation on the same simulation."""

    alternative: str  # NOW_T | BASE
    saving: Decimal  # simple rule's total cost − recommendation's total cost (negative = the rule is cheaper)


@dataclass(frozen=True)
class BenchmarkTotal:
    clients: int
    simple_cost: Decimal
    recommended_cost: Decimal
    saving: Decimal
    simple_orders: int
    recommended_orders: int


@dataclass(frozen=True)
class ClientResult:
    name: str
    profile: str
    tax_regime: str
    note: str
    status: str  # ok | data_error | policy_error
    issues: list[Issue]
    valuation: Valuation | None
    horizon_end: date | None
    reserve_days: int | None
    earmark_today: Decimal | None
    triggers: list[TriggerOut]
    alternatives: list[AlternativeOut]
    recommended: str | None
    ranking: RankingOut | None
    uncertainty: list[UncertaintyOut]
    outcome: OutcomeOut
    monitoring: list[dict]
    reserve_bridge: ReserveBridge | None = None
    summary: Summary | None = None
    explanations: list[Explanation] = field(default_factory=list)
    stress: StressOut | None = None
    benchmark: Benchmark | None = None


@dataclass(frozen=True)
class EvaluationResult:
    model_version: str
    valuation_date: date
    source: str
    assumptions: dict
    issues: list[Issue]
    clients: list[ClientResult]
    benchmark: BenchmarkTotal | None = None  # totals over clients with a result
