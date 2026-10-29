"""Engine-level dataset validation (doc 08 §12). The workbook adapter adds sheet/cell references; this check runs on
every ``evaluate()`` so that no entry point (API, CLI, tests) can bypass it. Global errors block every client;
client errors block only that client."""

from decimal import Decimal

from .model import CASH, CZK, FO, SRO, Dataset
from .results import Issue

MAX_LOTS = 1_000
MAX_FLOWS = 500
MAX_UNITS = 10**9
MAX_AMOUNT = Decimal(10) ** 13  # 10 trillion in any currency
MAX_CLIENTS = 200


def validate_dataset(ds: Dataset) -> list[Issue]:
    out: list[Issue] = []

    def err(code, msg, client=None):
        out.append(Issue("error", code, msg, None, None, client))

    if ds.fx.get(CZK) != 1:
        err("bad_fx", "Kurz CZK musí být 1.")
    for c, v in ds.fx.items():
        if not (0 < v < MAX_AMOUNT):
            err("bad_fx", f"Neplatný kurz {c}.")
    tickers = [i.ticker for i in ds.instruments]
    if not tickers:
        err("no_instruments", "Data neobsahují žádný instrument.")
    if len(set(tickers)) != len(tickers):
        err("duplicate", "Duplicitní ticker instrumentu.")
    for i in ds.instruments:
        if i.currency not in ds.fx:
            err("missing_fx", f"Chybí kurz pro měnu {i.currency} (instrument {i.ticker}).")
        if not (0 < i.price < MAX_AMOUNT):
            err("bad_price", f"Neplatná cena instrumentu {i.ticker}.")
        if not (0 <= i.settlement_days <= 10):
            err("bad_settlement", f"Neplatná lhůta vypořádání instrumentu {i.ticker}.")
    if not ds.clients or len(ds.clients) > MAX_CLIENTS:
        err("no_clients", "Počet klientů musí být 1 až 200.")
    names = [c.name for c in ds.clients]
    if len(set(names)) != len(names):
        err("duplicate", "Duplicitní jméno klienta.")
    if sum(len(c.lots) for c in ds.clients) > MAX_LOTS:
        err("too_many_lots", f"Více než {MAX_LOTS} pozic.")
    if sum(len(c.flows) for c in ds.clients) > MAX_FLOWS:
        err("too_many_flows", f"Více než {MAX_FLOWS} plánovaných toků.")
    if out:
        return out

    for c in ds.clients:
        if c.tax_regime not in (FO, SRO):
            err("bad_regime", f"Neznámý daňový režim „{c.tax_regime}“.", c.name)
        if set(c.targets) != set(tickers) | {CASH}:
            err("targets_keys", "Cílové váhy neodpovídají instrumentům.", c.name)
        elif sum(c.targets.values(), Decimal(0)) != 100 or any(not (0 <= v <= 100) for v in c.targets.values()):
            err("targets_sum", "Cílové váhy musí být 0–100 % a dát součet 100 %.", c.name)
        for lot in c.lots:
            if lot.ticker not in tickers:
                err("unknown_ticker", f"Neznámý ticker „{lot.ticker}“.", c.name)
            elif lot.acquired > ds.valuation_date:
                err("bad_date", f"Nákup {lot.ticker} {lot.acquired.isoformat()} je po datu ocenění.", c.name)
            elif not (0 < lot.units <= MAX_UNITS) or not (0 < lot.buy_price < MAX_AMOUNT):
                err("bad_units", f"Neplatný počet kusů nebo nákupní cena ({lot.ticker}).", c.name)
        ccys = [b.currency for b in c.cash]
        if len(set(ccys)) != len(ccys):
            err("duplicate", "Duplicitní zůstatek hotovosti ve stejné měně.", c.name)
        for b in c.cash:
            if b.currency not in ds.fx:
                err("missing_fx", f"Měna {b.currency} nemá kurz.", c.name)
            elif not (0 <= b.amount < MAX_AMOUNT):
                err("negative_cash" if b.amount < 0 else "bad_amount", "Neplatný zůstatek hotovosti.", c.name)
        for f in c.flows:
            if f.amount == 0 or abs(f.amount) >= MAX_AMOUNT:
                err("bad_amount", "Neplatná částka plánovaného toku.", c.name)
    return out
