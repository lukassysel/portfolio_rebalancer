"""Czech business-day calendar (zákon č. 245/2000 Sb.): weekends and public holidays.

Exchange and TARGET calendars are deliberately ignored (doc 08 §2, documented assumption).
"""

from datetime import date, timedelta
from functools import lru_cache

_FIXED = [(1, 1), (5, 1), (5, 8), (7, 5), (7, 6), (9, 28), (10, 28), (11, 17), (12, 24), (12, 25), (12, 26)]


def _easter_sunday(year: int) -> date:
    # Anonymous Gregorian algorithm (Meeus/Jones/Butcher).
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=None)
def holidays(year: int) -> frozenset[date]:
    days = {date(year, m, d) for m, d in _FIXED}
    easter = _easter_sunday(year)
    days.add(easter + timedelta(days=1))  # Velikonoční pondělí
    if year >= 2016:
        days.add(easter - timedelta(days=2))  # Velký pátek
    return frozenset(days)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def add_business_days(d: date, n: int) -> date:
    """n-th business day after d (n >= 0; n = 0 returns d unchanged)."""
    while n > 0:
        d += timedelta(days=1)
        if is_business_day(d):
            n -= 1
    return d


def sub_business_days(d: date, n: int) -> date:
    """n-th business day before d."""
    while n > 0:
        d -= timedelta(days=1)
        if is_business_day(d):
            n -= 1
    return d


def on_or_before(d: date) -> date:
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def on_or_after(d: date) -> date:
    while not is_business_day(d):
        d += timedelta(days=1)
    return d


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 February
        return d.replace(year=d.year + years, day=28)


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)
