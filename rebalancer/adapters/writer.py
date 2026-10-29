"""Write a dataset + client strategies back to an .xlsx in the same format the importer reads (round trip)."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font

from ..engine.model import CASH, Dataset, Policy
from .workbook import SETTLEMENT_HEADER, STRATEGY_COLUMNS


def write_workbook(ds: Dataset, policies: dict[str, Policy]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Čti mě"
    d = ds.valuation_date
    for line in ["Rebalancování klientských portfolií – data", "", f"Ocenění k datu: {d.day}. {d.month}. {d.year}", "",
                 "Listy: Instrumenty, Kurzy, Klienti (cílové váhy v % celkového majetku vč. hotovosti), Pozice,",
                 "Hotovost, Cash flow (kladné = vklad, záporné = výběr), Strategie (parametry rebalancování klienta)."]:
        ws.append([line])

    def sheet(title, header, rows):
        s = wb.create_sheet(title)
        s.append(header)
        for c in s[1]:
            c.font = Font(bold=True)
        for r in rows:
            s.append(r)
        return s

    sheet("Instrumenty", ["Ticker", "Název", "ISIN", "Měna", "Třída aktiv", "Cena (v měně instrumentu)", SETTLEMENT_HEADER],
          [[i.ticker, i.name, i.isin, i.currency, i.asset_class, i.price, i.settlement_days] for i in ds.instruments])
    sheet("Kurzy", ["Měnový pár", "Kurz (CZK za 1 jednotku)"],
          [[f"{c}/CZK", v] for c, v in ds.fx.items() if c != "CZK"])
    tickers = [i.ticker for i in ds.instruments]
    sheet("Klienti", ["Klient", "Profil", "Daňový režim"] + [f"Cíl {t} %" for t in tickers] + ["Cíl hotovost %", "Poznámka"],
          [[c.name, c.profile, c.tax_regime] + [(policies.get(c.name) or c).targets[t] for t in tickers]
           + [(policies.get(c.name) or c).targets[CASH], c.note] for c in ds.clients])
    pos = sheet("Pozice", ["Klient", "Ticker", "Datum nákupu", "Počet kusů", "Nákupní cena (v měně instrumentu)"],
                [[c.name, l.ticker, l.acquired, l.units, l.buy_price] for c in ds.clients for l in c.lots])
    sheet("Hotovost", ["Klient", "Měna", "Zůstatek"], [[c.name, b.currency, b.amount] for c in ds.clients for b in c.cash])
    cf = sheet("Cash flow", ["Klient", "Datum", "Typ", "Částka CZK", "Poznámka"],
               [[c.name, f.date, f.kind or ("Vklad" if f.amount > 0 else "Výběr"), f.amount, f.note]
                for c in ds.clients for f in c.flows])
    for s, col in ((pos, "C"), (cf, "B")):
        for cell in s[col][1:]:
            cell.number_format = "D. M. YYYY"
    rows = []
    for c in ds.clients:
        p = policies.get(c.name)
        if p is None:
            continue
        rows.append([c.name] + [getattr(p, f) for _, f, _ in STRATEGY_COLUMNS])
    sheet("Strategie", ["Klient"] + [h for h, _, _ in STRATEGY_COLUMNS], rows)
    for s in wb.worksheets[1:]:
        for col in s.columns:
            s.column_dimensions[col[0].column_letter].width = max(12, min(48, max(len(str(c.value or "")) for c in col) + 2))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
