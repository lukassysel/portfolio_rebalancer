"""One JSON writer for API and CLI: Decimals as plain-notation strings (never "5E+1"), dates as ISO strings."""

import json
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import TypeAdapter


def _plain(v: Any) -> Any:
    if isinstance(v, Decimal):
        s = format(v, "f")
        return "0" if s in ("-0", "0") or (s.lstrip("-").strip("0.") == "" and "." in s) else s
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    return v


def to_jsonable(obj: Any, tp: Any) -> Any:
    return _plain(TypeAdapter(tp).dump_python(obj, mode="python"))


def to_json_bytes(obj: Any, tp: Any) -> bytes:
    return json.dumps(to_jsonable(obj, tp), ensure_ascii=False, separators=(",", ":")).encode()
