import { useState } from 'react'
import type { ClientResult, EvaluationResult } from '../api/types'
import { Link } from 'react-router-dom'
import { ImportDialog } from '../components/ImportDialog'
import { downloadWorkbook } from '../api/client'
import { useApp } from '../state'
import { BandGauge, GaugeLegend } from '../components/BandGauge'
import { gaugesFor } from '../gauges'
import { czk, plural } from '../format'
import { OUTCOME_GROUP, QUEUE_ORDER, alt, nextStep, reason } from '../texts'
import { shortStep } from '../record'
import { SimpleRule, since } from '../components/Meaning'
import { compName } from '../texts'

export const STATUS_COLOR: Record<string, string> = {
  fix_data: 'var(--s-fix)', ensure_liquidity: 'var(--s-liq)', review: 'var(--s-review)', execute_now: 'var(--s-now)',
  wait: 'var(--s-wait)', check: 'var(--s-check)', no_action: 'var(--s-none)',
}

export function Overview() {
  const { result, snapshot, policies, stale, unsaved, markSaved, previous } = useApp()
  const [msg, setMsg] = useState<string | null>(null)
  const [importOpen, setImportOpen] = useState(false)
  if (!result || !snapshot) return null
  const asOf = result.valuation_date
  const groups = QUEUE_ORDER.map((code) => ({ code, clients: result.clients.filter((c) => c.outcome.code === code) }))
  // "today" = a decision code or any step of the recommended plan dated today (e.g. E's reserve sale while waiting)
  const hasToday = (c: (typeof result.clients)[number]) =>
    ['fix_data', 'ensure_liquidity', 'review', 'execute_now'].includes(c.outcome.code) ||
    !!alt(c, c.recommended)?.orders.some((o) => o.trade_date === asOf)
  const today = result.clients.filter(hasToday).length
  const later = result.clients.filter((c) => c.outcome.code === 'wait').length
  const calm = result.clients.filter((c) => !hasToday(c) && c.outcome.code !== 'wait').length
  return (
    <>
      <div className="overview-head">
        <h1>Přehled klientů</h1>
        <p className="tally" aria-label="Souhrn">
          <span><b>{plural(today, 'klient', 'klienti', 'klientů')}</b> s úkolem dnes</span>
          <span><b>{plural(later, 'klient', 'klienti', 'klientů')}</b> s hlavním krokem později</span>
          <span><b>{plural(calm, 'klient', 'klienti', 'klientů')}</b> bez zásahu nebo jen ke kontrole</span>
          <span className="muted">celkem {plural(result.clients.length, 'klient', 'klienti', 'klientů')}</span>
        </p>
      </div>
      <div className="toolbar no-print">
        <button className="btn" onClick={() => downloadWorkbook(snapshot.dataset, policies).then(markSaved).catch((e) => setMsg((e as Error).message))}>
          Uložit data (Excel)
        </button>
        <button className="btn" onClick={() => setImportOpen(true)}>Načíst data (Excel)</button>
        {unsaved && <span className="stale" role="status">Neuložené změny – uložte je tlačítkem „Uložit data (Excel)“.</span>}
        {msg && <span role="status" className="muted">{msg}</span>}
      </div>
      {importOpen && <ImportDialog onClose={() => setImportOpen(false)} />}
      <GaugeLegend projected />
      {groups.filter((g) => g.clients.length).map((g) => (
        <section key={g.code} className="queue-group" aria-labelledby={`g-${g.code}`}>
          <div className="group-title">
            <span className="mark" style={{ ['--c' as string]: STATUS_COLOR[g.code] }} />
            <h2 id={`g-${g.code}`}>{OUTCOME_GROUP[g.code]}</h2>
            <span className="count">{plural(g.clients.length, 'klient', 'klienti', 'klientů')}</span>
          </div>
          {g.clients
            .slice()
            .sort((a, b) => (a.outcome.date ?? '9999').localeCompare(b.outcome.date ?? '9999'))
            .map((c) => {
              const step = nextStep(c)
              const rec = alt(c, c.recommended)
              const slug = encodeURIComponent(c.name)
              return (
                <article key={c.name} className="qrow" style={{ ['--c' as string]: STATUS_COLOR[c.outcome.code] }}>
                  <div className="who">
                    <Link to={`/klient/${slug}`}>{c.name}</Link>
                    <small>{c.tax_regime === 'FO' ? 'fyzická osoba' : 's.r.o.'}, majetek {czk(c.valuation?.nav, 0)}</small>
                    {previous && c.status === 'ok' && <Since c={c} previous={previous} asOf={asOf} />}
                  </div>
                  <div className="step-cell">
                    {stale[c.name] && <div className="stale" role="status">Neaktuální: rozpracovaná strategie obsahuje chybu – zobrazen poslední platný výsledek.</div>}
                    <div className="step">{shortStep(c.summary, c.outcome.label)}</div>
                    <div className="why">{reason(c)}</div>
                  </div>
                  <div className="when">
                    {step.when ? (<><span>{step.whenType}</span><b>{step.when}</b></>) : <span>—</span>}


                  </div>
                  <div className="cost">
                    <span>náklady (odhad)</span>
                    <b>{rec && c.recommended !== 'BASE' ? czk(rec.total_cost, 0) : czk(0, 0)}</b>
                    {rec && rec.tax === null && c.recommended !== 'BASE' && <span>daň s.r.o. nelze určit</span>}
                    {rec && rec.tax !== null && c.recommended !== 'BASE' && <span>z toho daň {czk(rec.tax, 0)}</span>}
                  </div>
                  <div className="gauges">
                    {gaugesFor(c, asOf).filter((gd) => gd.breach).map((gd) => <BandGauge key={gd.key} g={gd} />)}
                  </div>
                </article>
              )
            })}
        </section>
      ))}
      <SimpleRule result={result} />
    </>
  )
}

// compared with the evaluation before the last import (data of the previous month)
function Since({ c, previous, asOf }: { c: ClientResult; previous: EvaluationResult; asOf: string }) {
  const p = previous.clients.find((x) => x.name === c.name)
  const d = since(p, previous.valuation_date, c, asOf)
  const names = (ks: string[]) => ks.map(compName).join(', ')
  const text = !d.known ? 'nový klient'
    : d.added.length ? `nově mimo pásmo: ${names(d.added)}`
    : d.outcome ? `změna: ${d.outcome}`
    : d.kept.length ? `mimo pásmo i minule: ${names(d.kept)}`
    : d.gone.length ? `zpět v pásmu: ${names(d.gone)}` : 'beze změny od minula'
  return <small className={`since${d.added.length || d.outcome ? ' new' : ''}`}>{text}</small>
}
