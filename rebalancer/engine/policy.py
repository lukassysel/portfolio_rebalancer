"""Client strategy: defaults, the editable parameters and validation (doc 08 §4)."""

from dataclasses import dataclass
from decimal import Decimal

from .model import CASH, Policy

D = Decimal

# The parameters a manager edits per client; the others keep their documented defaults (model.Policy).
EDITABLE = ["band_abs", "band_rel", "min_trade", "max_wait_days"]

# (field, min, max) — validation ranges for editable numeric parameters.
RANGES: dict[str, tuple[Decimal, Decimal]] = {
    "band_abs": (D("0.25"), D(20)),
    "band_rel": (D(5), D(100)),
    "equity_band": (D("0.5"), D(20)),
    "idle_cash_tol": (D("0.5"), D(20)),
    "inner_band": (D(0), D(100)),
    "planning_months": (D(1), D(24)),
    "reserve_days": (D(14), D(366)),  # ≥ 10 business days is re-checked on the real calendar
    "min_trade": (D(0), D(1000000)),
    "max_wait_days": (D(0), D(180)),
    "wait_dev_cap": (D(0), D(100)),
    "min_saving_czk": (D(0), D(100000000)),
    "min_saving_pct": (D(0), D(100)),
    "min_cash_pct": (D(0), D(20)),
    "min_cash_czk": (D(0), D(100000000)),
}


@dataclass(frozen=True)
class PolicyIssue:
    field: str
    code: str
    params: dict


def default_policy(targets: dict[str, Decimal]) -> Policy:
    return Policy(targets=dict(targets))


def validate_policy(policy: Policy, tickers: list[str]) -> list[PolicyIssue]:
    issues: list[PolicyIssue] = []
    expected = set(tickers) | {CASH}
    if set(policy.targets) != expected:
        issues.append(PolicyIssue("targets", "targets_keys", {"expected": sorted(expected)}))
        return issues
    for k, v in policy.targets.items():
        if not (D(0) <= v <= D(100)):
            issues.append(PolicyIssue(f"targets.{k}", "out_of_range", {"min": "0", "max": "100", "value": str(v)}))
    total = sum(policy.targets.values(), D(0))
    if total != D(100):
        issues.append(PolicyIssue("targets", "targets_sum", {"sum": str(total)}))
    for name, (lo, hi) in RANGES.items():
        v = D(getattr(policy, name))
        if not (lo <= v <= hi):
            issues.append(PolicyIssue(name, "out_of_range", {"min": str(lo), "max": str(hi), "value": str(v)}))
    return issues


def band(policy: Policy, target: Decimal) -> Decimal:
    """Hybrid tolerance b = min(abs, rel × t); components with a 0 % target have b = 0 (doc 08 §4)."""
    if target <= 0:
        return D(0)
    return min(policy.band_abs, policy.band_rel / 100 * target)
