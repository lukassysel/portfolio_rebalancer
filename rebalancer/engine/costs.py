"""Shared transaction-cost, FX and tax-date helpers (doc 05, doc 08 §5)."""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from . import calendar as cal
from .model import Assumptions

CENT = Decimal("0.01")


def commission(units: int | Decimal, price: Decimal, a: Assumptions) -> Decimal:
    """Per order: max(minimum, rate × gross), rounded half-up to 0.01 of the trade currency; 0 for 0 units."""
    if not units:
        return Decimal(0)
    return max(a.commission_min, Decimal(units) * price * a.commission_rate).quantize(CENT, ROUND_HALF_UP)


def fx_cost_czk(source: Decimal, fx_source: Decimal, a: Assumptions) -> Decimal:
    return (source * fx_source * a.fx_cost).quantize(CENT, ROUND_HALF_UP)


def acquisition_date(purchase: date, a: Assumptions) -> date:
    """D-TAX-1: legal acquisition = credit to the owner's account ≈ purchase + settlement lag."""
    return cal.add_business_days(purchase, a.acquisition_settlement_days)


def first_exempt_trade_date(purchase: date, a: Assumptions, raw: bool = False) -> date:
    """First trade date on which a sale is exempt under the 3-year time test (ZDP §4(1)(u)).

    Default (D-TAX-1, conservative): strictly after acquisition (purchase + 2 bd) + 3 years, first business day.
    ``raw=True`` is the uncertainty-gate reading: strictly after the purchase date + 3 years.
    """
    start = purchase if raw else acquisition_date(purchase, a)
    return cal.on_or_after(cal.add_years(start, a.time_test_years) + timedelta(days=1))
