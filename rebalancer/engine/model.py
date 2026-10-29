"""Immutable input model: dataset (actual holdings), client policies and system assumptions.

Money and prices are ``Decimal``; units are integers. Percentages are expressed in percent (5 = 5 %).
The engine never mutates these objects (doc 08 §1.4: actual holdings are input only).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

CASH = "CASH"
CZK = "CZK"
FO = "FO"
SRO = "s.r.o."


@dataclass(frozen=True)
class Instrument:
    ticker: str
    name: str
    isin: str
    currency: str
    asset_class: str
    price: Decimal
    settlement_days: int = 2

    @property
    def is_equity(self) -> bool:
        """Equity sleeves form the total-equity aggregate (workbook asset class „Akcie …“)."""
        return self.asset_class.strip().lower().startswith("akcie")


@dataclass(frozen=True)
class Lot:
    ticker: str
    acquired: date
    units: int
    buy_price: Decimal


@dataclass(frozen=True)
class CashBalance:
    currency: str
    amount: Decimal


@dataclass(frozen=True)
class Flow:
    date: date
    amount: Decimal  # CZK; positive = deposit (vklad), negative = withdrawal (výběr)
    kind: str = ""
    note: str = ""


@dataclass(frozen=True)
class Client:
    name: str
    profile: str
    tax_regime: str  # "FO" or "s.r.o."
    targets: dict[str, Decimal]  # ticker -> %, plus CASH
    note: str = ""
    lots: list[Lot] = field(default_factory=list)
    cash: list[CashBalance] = field(default_factory=list)
    flows: list[Flow] = field(default_factory=list)


@dataclass(frozen=True)
class Dataset:
    valuation_date: date
    instruments: list[Instrument]
    fx: dict[str, Decimal]  # CZK per 1 unit of currency; CZK = 1
    clients: list[Client]
    source: str = ""


@dataclass(frozen=True)
class Policy:
    """Per-client rebalancing policy (doc 08 §4). Legislation is never a policy parameter."""

    targets: dict[str, Decimal]
    band_abs: Decimal = Decimal(5)  # p. b.
    band_rel: Decimal = Decimal(25)  # % of the target weight
    equity_band: Decimal = Decimal(5)  # p. b., aggregate of all equity instruments
    idle_cash_tol: Decimal = Decimal(5)  # p. b., when the cash target is 0 %
    inner_band: Decimal = Decimal(50)  # partial destination: target ± inner % of the band (0 = to target)
    planning_months: int = 6
    reserve_days: int = 90
    min_trade: Decimal = Decimal(25000)  # Kč
    max_wait_days: int = 45
    wait_dev_cap: Decimal = Decimal(15)  # p. b.
    min_saving_czk: Decimal = Decimal(10000)
    min_saving_pct: Decimal = Decimal("0.05")  # % of NAV
    min_cash_pct: Decimal = Decimal("0.5")  # cash kept in CZK when the plan trades: max(% of NAV, Kč amount)
    min_cash_czk: Decimal = Decimal(10000)


@dataclass(frozen=True)
class Assumptions:
    """System-level model assumptions (doc 08 §2), echoed in every result."""

    commission_rate: Decimal = Decimal("0.0015")
    commission_min: Decimal = Decimal(10)  # in the trade currency
    fx_cost: Decimal = Decimal("0.005")
    fx_lag_days: int = 1
    tax_rate: Decimal = Decimal("0.15")
    tax_rate_high: Decimal = Decimal("0.23")
    corporate_tax_rate: Decimal = Decimal("0.21")
    receipts_exemption: Decimal = Decimal(100000)
    time_test_years: int = 3
    acquisition_settlement_days: int = 2  # D-TAX-1: acquisition = purchase + 2 business days
    monitor_band_ratio: Decimal = Decimal("0.75")
    monitor_days: int = 30
    stress_equity_drop: Decimal = Decimal(20)  # % – illustrative equity fall for the risk line (not a forecast)
