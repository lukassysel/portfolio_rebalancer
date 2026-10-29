"""Economic meaning of deviations, the stress line and the simple-rule benchmark: derived from the same evaluation."""

from decimal import Decimal as D


def by_name(res):
    return {c.name: c for c in res.clients}


def test_band_excess_is_deviation_beyond_the_band_edge_in_pp_and_czk(result):
    for c in result.clients:
        nav, ear = c.valuation.nav, c.earmark_today
        for t in c.triggers:
            if t.date != result.valuation_date or t.rule in ("L1", "ALL_RESERVED"):
                continue
            assert t.excess == abs(t.deviation) - t.band > 0
            assert t.excess_czk == t.excess / 100 * (nav if t.measure == "A" else nav - ear)


def test_reserve_view_shows_breaches_the_total_asset_view_misses(result):
    b = by_name(result)["Klient B"]
    vwce = next(x for x in b.valuation.components if x.key == "VWCE")
    assert not vwce.breach  # inside the band on total assets …
    assert any(t.scope == "VWCE" and t.measure == "B" for t in b.triggers)  # … outside after the withdrawal reserve


def test_stress_is_equity_value_times_the_assumed_drop(result):
    k = D(result.assumptions["stress_equity_drop"]) / 100
    for c in result.clients:
        s, eq = c.stress, c.valuation.equity
        assert s.loss == eq.value * k and s.loss_pct == eq.weight * k
        assert s.target_pct == eq.target * k
        assert (s.after_pct is None) == (c.recommended == "BASE")


def test_simple_rule_trades_fully_to_target_only_on_a_total_asset_breach(result):
    for c in result.clients:
        v = c.valuation
        breached = v.equity.breach or any(x.breach for x in v.components)
        assert c.benchmark.alternative == ("NOW_T" if breached else "BASE")
        cost = {a.id: a.total_cost for a in c.alternatives}
        assert c.benchmark.saving == cost[c.benchmark.alternative] - cost[c.recommended]


def test_benchmark_totals_add_up(result):
    t = result.benchmark
    alts = [({a.id: a for a in c.alternatives}, c) for c in result.clients]
    assert t.simple_cost == sum(by[c.benchmark.alternative].total_cost for by, c in alts)
    assert t.recommended_cost == sum(by[c.recommended].total_cost for by, c in alts)
    assert t.saving == t.simple_cost - t.recommended_cost
    assert t.recommended_orders == sum(by[c.recommended].order_count for by, c in alts)


def test_no_action_client_equals_the_simple_rule(result):
    c = by_name(result)["Klient C"]
    assert c.recommended == c.benchmark.alternative == "BASE" and c.benchmark.saving == 0
