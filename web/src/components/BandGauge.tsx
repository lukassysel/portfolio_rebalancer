// Tolerance-band gauge: target, permitted band, current weight (A), projected weight (B) and the weight
// after the proposal. Pure geometry for display; all values come from the engine.
import { compName } from '../texts'
import { pct, pp } from '../format'

export type GaugeData = {
  key: string
  target: string
  low: string
  high: string
  current: string
  projected?: string | null
  after?: string | null
  breach: boolean // outside the band today in any view (total assets or after the withdrawal reserve)
  breachTotal: boolean // outside on today's total-asset weight (the drawn "today" marker)
}

export function BandGauge({ g, big = false }: { g: GaugeData; big?: boolean }) {
  const t = Number(g.target)
  const lo = Number(g.low)
  const hi = Number(g.high)
  const vals = [Number(g.current), g.projected ? Number(g.projected) : t, g.after ? Number(g.after) : t]
  const reach = Math.max(hi - t, t - lo, ...vals.map((v) => Math.abs(v - t)), 1) * 1.18
  const min = t - reach
  const x = (v: number) => ((v - min) / (2 * reach)) * 100
  const h = big ? 30 : 22
  const mid = h / 2
  const dev = Number(g.current) - t
  const label = `${compName(g.key)}: dnes ${pct(g.current)}, cíl ${pct(g.target)}, pásmo ${pct(g.low)}–${pct(g.high)}${
    g.projected ? `, po odečtení rezervy ${pct(g.projected)}` : ''
  }${g.after ? `, po návrhu ${pct(g.after)}` : ''}${g.breach ? (g.breachTotal ? ', mimo pásmo' : ', mimo pásmo po odečtení rezervy') : ''}`
  return (
    <div className={`${big ? 'gauge big' : 'gauge'}${g.breach ? '' : ' ok'}`} title={label}>
      <span className="gl">{compName(g.key)}</span>
      <svg viewBox={`0 0 100 ${h}`} preserveAspectRatio="none" role="img" aria-label={label}>
        <line x1="0" x2="100" y1={mid} y2={mid} stroke="#c9d2cf" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        <rect x={x(lo)} width={Math.max(x(hi) - x(lo), 0.4)} y={mid - h * 0.28} height={h * 0.56} fill="var(--band)"
          stroke="var(--band-edge)" strokeWidth="1" vectorEffect="non-scaling-stroke" rx="1" />
        <line x1={x(t)} x2={x(t)} y1={mid - h * 0.42} y2={mid + h * 0.42} stroke="var(--ink)" strokeWidth="2"
          vectorEffect="non-scaling-stroke" />
        {g.projected && (
          <line x1={x(Number(g.projected))} x2={x(Number(g.projected))} y1={mid - h * 0.4} y2={mid + h * 0.4}
            stroke="var(--s-liq)" strokeWidth="2" strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
        )}
        {g.after && (
          <line x1={x(Number(g.after))} x2={x(Number(g.after))} y1={mid - h * 0.46} y2={mid + h * 0.46}
            stroke="var(--accent)" strokeWidth="3" vectorEffect="non-scaling-stroke" />
        )}
        <line x1={x(t)} x2={x(Number(g.current))} y1={mid} y2={mid}
          stroke={g.breachTotal ? 'var(--breach)' : 'var(--ink-2)'} strokeWidth={big ? 4 : 3} vectorEffect="non-scaling-stroke" />
        <line x1={x(Number(g.current))} x2={x(Number(g.current))} y1={mid - h * 0.3} y2={mid + h * 0.3}
          stroke={g.breachTotal ? 'var(--breach)' : 'var(--ink-2)'} strokeWidth={big ? 5 : 4} vectorEffect="non-scaling-stroke" />
      </svg>
      {!big && g.breach && !g.breachTotal && <span className="gnote">po odečtení rezervy</span>}
      {big && (
        <span className="gv">
          <b>{pct(g.current)}</b> {g.breach ? <span className="tag bad">{g.breachTotal ? 'mimo pásmo' : 'mimo pásmo po odečtení rezervy'}</span> : null}
          <small>
            cíl {pct(g.target, 1)}, {pp(dev)}
          </small>
        </span>
      )}
    </div>
  )
}

export function GaugeLegend({ projected, after }: { projected?: boolean; after?: boolean }) {
  return (
    <div className="legend" aria-hidden="true">
      <span><i style={{ width: 18, height: 10, background: 'var(--band)', border: '1px solid var(--band-edge)' }} />povolené pásmo</span>
      <span><i style={{ width: 2, height: 14, background: 'var(--ink)' }} />cíl</span>
      <span><i style={{ width: 14, height: 4, background: 'var(--ink-2)' }} />dnes (z celého majetku)</span>
      <span><i style={{ width: 14, height: 4, background: 'var(--breach)' }} />dnes, mimo pásmo</span>
      {projected && <span><i style={{ width: 2, height: 14, borderLeft: '2px dashed var(--s-liq)' }} />po odečtení rezervy na výběry</span>}
      {after && <span><i style={{ width: 3, height: 14, background: 'var(--accent)' }} />po provedení návrhu</span>}
    </div>
  )
}
