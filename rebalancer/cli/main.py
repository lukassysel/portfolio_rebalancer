"""`rebalancer evaluate [data.xlsx] [--policies p.json] [--out result.json]` — same evaluate() and JSON as the API."""

import argparse
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from ..adapters import WorkbookError, load_demo_book, read_book
from ..engine import Policy, evaluate
from ..engine.results import EvaluationResult
from ..serialize import to_json_bytes


def evaluate_file(path: str | None, policies_path: str | None = None) -> bytes:
    if path:
        ds, issues, policies = read_book(Path(path).read_bytes(), Path(path).name)
    else:
        ds, issues, policies = load_demo_book()
    if policies_path:
        raw = json.loads(Path(policies_path).read_text())
        policies.update(TypeAdapter(dict[str, Policy]).validate_python(raw))
    result = evaluate(ds, policies, issues=issues)
    return to_json_bytes(result, EvaluationResult)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="rebalancer", description="Vyhodnocení portfolií (stejný engine jako web).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ev = sub.add_parser("evaluate", help="vyhodnotit sešit (bez argumentu ukázková data)")
    ev.add_argument("workbook", nargs="?")
    ev.add_argument("--policies", help="JSON se strategiemi {klient: Policy}")
    ev.add_argument("--out", help="výstupní JSON (jinak stdout)")
    ev.add_argument("--summary", action="store_true", help="vypsat stručný přehled místo JSON")
    args = ap.parse_args(argv)
    try:
        data = evaluate_file(args.workbook, args.policies)
    except WorkbookError as e:
        for i in e.issues:
            print(f"CHYBA {i.sheet or ''}!{i.cell or ''}: {i.message}", file=sys.stderr)
        return 2
    if args.summary:
        res = json.loads(data)
        for c in res["clients"]:
            print(f"{c['name']}: {c['outcome']['label']} (doporučeno {c['recommended']})")
        return 0
    if args.out:
        Path(args.out).write_bytes(data)
    else:
        sys.stdout.buffer.write(data + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
