import type { Alternative, ClientResult } from './api/types'
import type { GaugeData } from './components/BandGauge'

/** Gauge rows for a client: instruments (target > 0 or held), the equity aggregate and cash.
 *  "after" = weights (A) at the alternative's completion checkpoint, as returned by the engine. */
export function gaugesFor(c: ClientResult, asOf: string, after?: Alternative): GaugeData[] {
  const v = c.valuation
  if (!v) return []
  const base = c.alternatives.find((a) => a.id === 'BASE')
  const today = base?.checkpoints.find((k) => k.date === asOf)
  const hasReserve = Number(c.earmark_today ?? 0) > 0
  const done = after?.checkpoints.find((k) => k.date === after.compliance_from)
  // breached today in any view the engine checks (total assets, after the withdrawal reserve, cash net of reserve)
  const outToday = new Set(c.triggers.filter((t) => t.date === asOf && t.rule !== 'L1').map((t) => t.scope))
  const out: GaugeData[] = []
  for (const comp of v.components) {
    if (comp.key === 'CASH') continue
    if (Number(comp.target) === 0 && Number(comp.value) === 0) continue
    out.push({
      key: comp.key, target: comp.target, low: comp.band_low, high: comp.band_high, current: comp.weight,
      breach: comp.breach || outToday.has(comp.key), breachTotal: comp.breach,
      projected: hasReserve ? today?.weights_b?.[comp.key] ?? null : null,
      after: after && after.id !== 'BASE' ? done?.weights_a?.[comp.key] ?? null : null,
    })
  }
  const eq = v.equity
  out.push({
    key: 'EQ', target: eq.target, low: eq.band_low, high: eq.band_high, current: eq.weight, breach: eq.breach || outToday.has('EQ'),
    breachTotal: eq.breach,
    projected: hasReserve ? today?.equity_b ?? null : null,
    after: after && after.id !== 'BASE' ? done?.equity_a ?? null : null,
  })
  const cash = v.components.find((x) => x.key === 'CASH')!
  out.push({
    key: 'CASH', target: cash.target, low: cash.band_low, high: cash.band_high, current: cash.weight,
    breach: cash.breach || outToday.has('CASH'), breachTotal: cash.breach,
    projected: hasReserve ? today?.cash_net ?? null : null,
    after: null,
  })
  return out
}
