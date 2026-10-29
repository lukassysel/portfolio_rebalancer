"""Unit tests with hand-checkable arithmetic: calendar, fees, FX, time test."""

from datetime import date
from decimal import Decimal as D

import pytest

from rebalancer.engine import calendar as cal
from rebalancer.engine.costs import commission, first_exempt_trade_date, fx_cost_czk
from rebalancer.engine.model import Assumptions

A = Assumptions()


@pytest.mark.parametrize("d", [date(2026, 10, 28), date(2026, 11, 17), date(2026, 12, 24), date(2026, 12, 25),
                               date(2026, 12, 26), date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29),
                               date(2026, 5, 1), date(2026, 7, 6), date(2026, 9, 28)])
def test_czech_holidays(d):
    assert not cal.is_business_day(d)


def test_easter_2027():
    # Good Friday 26 March 2027, Easter Monday 29 March 2027
    assert date(2027, 3, 26) in cal.holidays(2027) and date(2027, 3, 29) in cal.holidays(2027)


def test_business_day_arithmetic():
    assert cal.add_business_days(date(2026, 10, 23), 2) == date(2026, 10, 27)
    assert cal.add_business_days(date(2026, 10, 27), 1) == date(2026, 10, 29)  # skips 28 Oct
    assert cal.on_or_before(date(2026, 11, 1)) == date(2026, 10, 30)  # Sunday withdrawal → Friday
    assert cal.on_or_after(date(2026, 11, 21)) == date(2026, 11, 23)


def test_latest_sale_for_withdrawals():
    # value date − 1 bd (FX) − 2 bd (settlement): doc 08 §5 examples
    def latest(vd):
        return cal.sub_business_days(cal.sub_business_days(vd, 1), 2)
    assert latest(date(2027, 1, 15)) == date(2027, 1, 12)
    assert latest(date(2026, 12, 15)) == date(2026, 12, 10)
    assert latest(cal.on_or_before(date(2026, 11, 1))) == date(2026, 10, 26)


@pytest.mark.parametrize("units,price,expected", [(1, D(2000), D(10)), (1, D(20000), D(30)), (1, D(8000), D(12)),
                                                  (0, D(100), D(0)), (174, D("142.5"), D("37.19"))])
def test_commission(units, price, expected):
    assert commission(units, price, A) == expected


def test_fx_equation():
    # deliver EUR 1 000 from CZK at 24.30, 0.5 % cost: A = 1000 × 24.3 / 0.995 rounded up
    assert fx_cost_czk(D("24422.12"), D(1), A) == D("122.11")
    # frictionless EUR → USD cross rate 24.3/21
    assert (D(100) * D("24.3") / D(21)).quantize(D("0.01")) == D("115.71")


def test_time_test_d_tax_1():
    # E's lot bought 20 Nov 2023 → acquisition 22 Nov 2023 → exempt strictly after 22 Nov 2026 → Mon 23 Nov
    assert first_exempt_trade_date(date(2023, 11, 20), A) == date(2026, 11, 23)
    assert first_exempt_trade_date(date(2023, 11, 20), A, raw=True) == date(2026, 11, 23)
    # B's EUNA lot bought 16 Oct 2023 → acquisition 18 Oct → exempt from Mon 19 Oct 2026 (before valuation)
    assert first_exempt_trade_date(date(2023, 10, 16), A) == date(2026, 10, 19)
    # 29 February maps to 28 February
    assert first_exempt_trade_date(date(2024, 2, 27), A) == date(2027, 3, 1)
