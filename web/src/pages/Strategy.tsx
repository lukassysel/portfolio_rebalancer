// Per-client strategy editor (doc 09 §3 „Strategie“). Invalid input marks results stale and does not recalculate;
// a valid change recalculates and shows a change summary with „Vrátit změnu“.
import { useEffect, useMemo, useRef, useState } from 'react'
import { getMeta } from '../api/client'
import type { ClientResult, Meta, Policy } from '../api/types'
import { czk, num, pct } from '../format'
import { useApp } from '../state'
import { ALT_NAMES, alt, feeText, taxText } from '../texts'

type FieldDef = { key: keyof Policy; label: string; unit: string; help: string; int?: boolean }

// The four parameters a manager sets per client; everything else is a documented default (listed on the right).
const MAIN: FieldDef[] = [
  { key: 'band_abs', label: 'Absolutní tolerance', unit: 'p. b.', help: 'Největší dovolená odchylka váhy od cíle v procentních bodech.' },
  { key: 'band_rel', label: 'Relativní tolerance', unit: '% cílové váhy', help: 'Pásmo jako podíl cílové váhy; použije se užší z obou tolerancí.' },
  { key: 'min_trade', label: 'Minimální obchod', unit: 'Kč', help: 'Menší obchody se nenavrhují (kromě nutné likvidity).' },
  { key: 'max_wait_days', label: 'Max. doba čekání', unit: 'dní', help: 'Čekání na vklad nebo časový test je přípustné jen do tohoto počtu dní.', int: true },
]

const toStr = (v: unknown) => (v === null || v === undefined ? '' : String(v).replace('.', ','))
const parse = (s: string) => s.trim().replace(/\s/g, '').replace(',', '.')
const isNum = (s: string) => /^-?\d+(\.\d+)?$/.test(parse(s))

type Summary = { before: Snap; after: Snap | null; prev: Policy }
type Snap = { label: string; rec: string | null; cost: string | null; orders: number; firstTrade: string | null }
const snap = (c: ClientResult): Snap => {
  const a = alt(c, c.recommended)
  return { label: c.outcome.label, rec: c.recommended, cost: a?.total_cost ?? null, orders: a?.order_count ?? 0, firstTrade: a?.first_order ?? null }
}

export function Strategy({ c }: { c: ClientResult }) {
  const { policies, setPolicy, resetPolicy, recalculating, snapshot, error, markStale } = useApp()
  const policy = policies[c.name]
  const TARGET_KEYS = useMemo(() => [...(snapshot?.dataset.instruments.map((i) => i.ticker) ?? []), 'CASH'], [snapshot])
  const [meta, setMeta] = useState<Meta | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [summary, setSummary] = useState<Summary | null>(null)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => { getMeta().then(setMeta).catch(() => undefined) }, [])
  // Re-sync the form whenever the policy changes from outside (undo, reset, loaded strategies, new data).
  useEffect(() => {
    if (!policy) return
    const d: Record<string, string> = {}
    for (const f of MAIN) d[f.key] = toStr(policy[f.key])
    for (const k of TARGET_KEYS) d[`t.${k}`] = toStr(policy.targets[k])
    setDraft((cur) => {
      const same = Object.keys(d).every((k) => parse(cur[k] ?? '') === parse(d[k]))
      return same ? cur : d
    })
  }, [policy, TARGET_KEYS])

  // After a recalculation completes, fill in the "after" side of the change summary.
  useEffect(() => {
    if (summary && !summary.after && !recalculating) setSummary({ ...summary, after: snap(c) })
  }, [recalculating, c, summary])

  const errors = useMemo(() => {
    const e: Record<string, string> = {}
    if (!meta) return e
    let sum = 0
    for (const k of TARGET_KEYS) {
      const v = draft[`t.${k}`] ?? ''
      if (!isNum(v) || Number(parse(v)) < 0 || Number(parse(v)) > 100) e[`t.${k}`] = 'Zadejte číslo 0–100.'
      else sum += Number(parse(v))
    }
    if (!Object.keys(e).length && Math.abs(sum - 100) > 1e-9) e.targets = `Součet cílových vah je ${num(sum)} %, musí být 100 %.`
    for (const f of MAIN) {
      const v = draft[f.key] ?? ''
      const [lo, hi] = meta.ranges[f.key as string] ?? ['0', '1e12']
      if (!isNum(v)) e[f.key] = 'Zadejte číslo.'
      else if (f.int && !/^\d+$/.test(parse(v))) e[f.key] = 'Zadejte celé číslo.'
      else if (Number(parse(v)) < Number(lo) || Number(parse(v)) > Number(hi)) e[f.key] = `Povolený rozsah ${toStr(lo)}–${toStr(hi)}.`
    }
    return e
  }, [draft, meta, TARGET_KEYS])

  const invalid = Object.keys(errors).length > 0
  useEffect(() => { markStale(c.name, invalid) }, [invalid, c.name, markStale])
  if (!policy) return null

  function build(d: Record<string, string>): Policy {
    const p: Record<string, unknown> = { ...policy, targets: {} }
    for (const f of MAIN) p[f.key] = f.int ? Number(parse(d[f.key])) : parse(d[f.key])
    const t: Record<string, string> = {}
    for (const k of TARGET_KEYS) t[k] = parse(d[`t.${k}`])
    p.targets = t
    return p as Policy
  }

  function change(key: string, value: string) {
    const d = { ...draft, [key]: value }
    setDraft(d)
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => commit(d), 450)
  }

  function commit(d: Record<string, string>) {
    // re-validate synchronously against the latest draft
    let sum = 0
    for (const k of TARGET_KEYS) { if (!isNum(d[`t.${k}`])) return; sum += Number(parse(d[`t.${k}`])) }
    if (Math.abs(sum - 100) > 1e-9) return
    for (const f of MAIN) {
      if (!isNum(d[f.key])) return
      const [lo, hi] = meta?.ranges[f.key as string] ?? ['0', '1e12']
      const x = Number(parse(d[f.key]))
      if (x < Number(lo) || x > Number(hi) || (f.int && !Number.isInteger(x))) return
    }
    setSummary({ before: snap(c), after: null, prev: policy })
    setPolicy(c.name, build(d))
  }

  const field = (f: FieldDef) => (
    <div className="field" key={f.key as string}>
      <label htmlFor={`f-${f.key as string}`}>{f.label} <span className="muted">({f.unit})</span></label>
      <input id={`f-${f.key as string}`} inputMode="decimal" value={draft[f.key as string] ?? ''} aria-invalid={!!errors[f.key as string]}
        aria-describedby={`h-${f.key as string}${errors[f.key as string] ? ` e-${f.key as string}` : ''}`} onChange={(e) => change(f.key as string, e.target.value)} />
      <span className="help" id={`h-${f.key as string}`}>{f.help}</span>
      {errors[f.key as string] && <span className="err" id={`e-${f.key as string}`} role="alert">{errors[f.key as string]}</span>}
    </div>
  )

  const d = meta?.default_policy
  const bandExample = (k: string) => {
    const t = Number(parse(draft[`t.${k}`] ?? '0'))
    const abs = Number(parse(draft.band_abs ?? '0'))
    const rel = Number(parse(draft.band_rel ?? '0'))
    if (!t) return 'cíl 0 % – nenakupuje se'
    const b = Math.min(abs, (rel / 100) * t)
    return `pásmo ${pct(t - b)}–${pct(t + b)}`
  }

  return (
    <div className="strategy">
      <div>
        <h2>Strategie klienta</h2>
        <p className="lead">
          Změna se po kontrole hned přepočítá. Neplatné hodnoty se nepřepočítají a výsledky se označí jako neaktuální.
          {recalculating && <span className="live" role="status"> Přepočítávám…</span>}
          {invalid && <span className="stale" role="status"> Výsledky jsou neaktuální – opravte zvýrazněná pole.</span>}
          {error && <span className="stale" role="alert"> {error}</span>}
        </p>
        {summary && (
          <div className="change-summary" role="status" aria-live="polite">
            <b>Dopad změny:</b>{' '}
            {summary.after ? (
              <>
                stav {summary.before.label} → <b>{summary.after.label}</b>; varianta {ALT_NAMES[summary.before.rec ?? ''] ?? '—'} →{' '}
                <b>{ALT_NAMES[summary.after.rec ?? ''] ?? 'žádná'}</b>; pokyny {summary.before.orders} → <b>{summary.after.orders}</b>;
                náklady {czk(summary.before.cost ?? 0)} → <b>{czk(summary.after.cost ?? 0)}</b>.
              </>
            ) : 'přepočítávám…'}
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button className="btn" onClick={() => { setPolicy(c.name, summary.prev); setSummary(null) }}>Vrátit změnu</button>
              <button className="btn" onClick={() => setSummary(null)}>Skrýt</button>
            </div>
          </div>
        )}
        <h3 style={{ marginTop: 20 }}>Cílové váhy (% celkového majetku)</h3>
        {TARGET_KEYS.map((k) => (
          <div className="field" key={k}>
            <label htmlFor={`t-${k}`}>{k === 'CASH' ? 'Hotovost' : k}</label>
            <input id={`t-${k}`} inputMode="decimal" value={draft[`t.${k}`] ?? ''} aria-invalid={!!errors[`t.${k}`]}
              aria-describedby={`ht-${k}${errors[`t.${k}`] ? ` et-${k}` : ''}${errors.targets ? ' e-targets' : ''}`}
              onChange={(e) => change(`t.${k}`, e.target.value)} />
            <span className="help" id={`ht-${k}`}>{k === 'CASH' ? 'Cílová hotovost (všechny měny)' : `${bandExample(k)} (náhled podle zadaných hodnot)`}</span>
            {errors[`t.${k}`] && <span className="err" id={`et-${k}`} role="alert">{errors[`t.${k}`]}</span>}
          </div>
        ))}
        {errors.targets && <p className="err stale" id="e-targets" role="alert">{errors.targets}</p>}
        <h3 style={{ marginTop: 20 }}>Tolerance a obchodování</h3>
        {MAIN.map(field)}
        <div style={{ marginTop: 18 }}>
          <button className="btn" onClick={() => { resetPolicy(c.name); setSummary(null) }}>Obnovit výchozí strategii</button>
        </div>
      </div>
      <aside className="fixed-rules" aria-labelledby="fixed-h">
        <h3 id="fixed-h">Pevná pravidla (needitovatelná)</h3>
        {d && (
          <ul>
            <li>Akcie celkem ±{num(d.equity_band, 0)} p. b.; nevyužitá hotovost při cíli 0 % nejvýš {num(d.idle_cash_tol, 0)} %.</li>
            <li>Složka mimo pásmo se vrací na cíl ± {num(d.inner_band, 0)} % pásma (částečné rebalancování).</li>
            <li>Rezerva na výběry splatné do {d.reserve_days} dnů; plán na {d.planning_months} měsíců.</li>
            <li>Čekání jen s odchylkou do {num(d.wait_dev_cap, 0)} p. b. a úsporou aspoň max({czk(d.min_saving_czk, 0)}; {num(d.min_saving_pct, 2)} % majetku).</li>
            <li>Když se obchoduje, zůstane minimální hotovost max({num(d.min_cash_pct, 1)} % majetku; {czk(d.min_cash_czk, 0)}).</li>
          </ul>
        )}
        <ul>
          <li>Daňová pravidla: {taxText(meta?.assumptions)}; u s.r.o. při prodeji daň nelze určit (chybí účetní hodnoty).</li>
          <li>{feeText(meta?.assumptions)}.</li>
          <li>Vypořádání obchodů T+2, převedená měna k dispozici následující pracovní den (český kalendář).</li>
          <li>Jen celé kusy, žádné krátké prodeje, hotovost nikdy pod nulou, vklad nelze použít před jeho připsáním.</li>
          <li>Nástroj s cílem 0 % se nikdy nenakupuje.</li>
        </ul>
      </aside>
    </div>
  )
}
