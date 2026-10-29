import { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import type { Alternative, ClientResult } from '../api/types'
import { Meaning } from '../components/Meaning'
import { BandGauge, GaugeLegend } from '../components/BandGauge'
import { czk, date, int, money, num, pct, pctTrim, plural, pp, units, weekday } from '../format'
import { gaugesFor } from '../gauges'
import { useApp } from '../state'
import {
  ALT_NAMES, STEP_REASON, TAX_STATUS, alt, compName, nextStep, reason, taxCols,
} from '../texts'
import { STATUS_COLOR } from './Overview'
import { SECTIONS, TAG_CLASS, explain, shortStep, tagText, type Tag } from '../record'
import { Strategy } from './Strategy'

const LEDGER_KIND = (kind: string, ref: string, amount: number) => {
  if (kind === 'start') return 'počáteční zůstatek'
  if (kind === 'flow') return `${amount > 0 ? 'vklad' : 'výběr'} ${date(ref)}`
  if (kind === 'sell') return `prodej ${ref.split(' ')[1]} (výnos po poplatku)`
  if (kind === 'buy') return `nákup ${ref.split(' ')[1]} (vč. poplatku)`
  const [purpose, r] = ref.split(':')
  return `převod měn – ${purpose === 'withdrawal' ? `na výběr ${date(r)}` : `na nákup ${r}`}`
}

export function Tags({ tags }: { tags?: Tag[] }) {
  return <span className="tags">{(tags ?? []).map((t, k) => <span key={k} className={`tag ${TAG_CLASS[t.kind] ?? ''}`}>{tagText(t)}</span>)}</span>
}

function Orders({ a, asOf }: { a: Alternative; asOf: string }) {
  if (!a.orders.length) return null
  return (
    <div className="orders">
      <table className="order-list" aria-label="Navržené pokyny a jejich důvody">
        <tbody>
          {a.orders.map((o, k) => (
            <tr key={k} className={o.conditional ? 'cond' : ''}>
              <td className="when">{o.trade_date === asOf ? 'dnes' : date(o.trade_date)}{o.conditional && <span className="muted"> podmíněně</span>}</td>
              <td className="what"><b>{o.side === 'BUY' ? 'Koupit' : 'Prodat'} {units(o.units)} {o.ticker}</b></td>
              <td className="n value">{czk(o.gross_czk, 0)}</td>
              <td><Tags tags={o.tags} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

const TABS = [
  { id: 'rozhodnuti', label: 'Rozhodnutí a varianty' },
  { id: 'obchody', label: 'Obchody a hotovost' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'strategie', label: 'Strategie' },
]

export function ClientPage() {
  const { name = '' } = useParams()
  const { result, snapshot } = useApp()
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') ?? 'rozhodnuti'
  const c = result?.clients.find((x) => x.name === name)
  const [selected, setSelected] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  useEffect(() => {
    if (!c) return
    if (selected && !c.alternatives.some((a) => a.id === selected)) {
      setNotice(`Varianta „${ALT_NAMES[selected]}“ po změně už neexistuje; zobrazuje se doporučená.`)
      setSelected(null)
    }
  }, [c, selected])

  useEffect(() => {
    document.title = `${name} – Rebalancování portfolií`
  }, [name])

  if (!result || !snapshot) return null
  if (!c) return <p>Klient „{name}“ v datech není. <Link to="/">Zpět na přehled</Link></p>
  const asOf = result.valuation_date
  const shown = alt(c, selected) ?? alt(c, c.recommended) ?? alt(c, 'BASE')

  const setTab = (id: string) => setParams(id === 'rozhodnuti' ? {} : { tab: id }, { replace: true })
  return (
    <>
      <nav className="crumbs" aria-label="Drobečková navigace"><Link to="/">Přehled</Link> / {c.name}</nav>
      <div className="client-head">
        <h1>{c.name}</h1>
        <span className="meta">{c.profile}</span>
        <span className="meta">{c.tax_regime === 'FO' ? 'fyzická osoba' : 'právnická osoba (s.r.o.)'}</span>
        {c.note && <span className="meta"><i>„{c.note}“</i></span>}
        <Link className="btn no-print" to={`/klient/${encodeURIComponent(c.name)}/upravit`}>Upravit údaje klienta</Link>
        {c.status === 'ok' && <Link className="btn no-print" to={`/klient/${encodeURIComponent(c.name)}/zprava`}>Zpráva pro klienta</Link>}
      </div>
      <Decision c={c} asOf={asOf} />
      {notice && <div className="notice" role="status">{notice}<button className="btn" onClick={() => setNotice(null)}>Rozumím</button></div>}
      {c.status === 'ok' && (
        <>
          <div className="tabs" role="tablist" aria-label="Části klienta">
            {TABS.map((t, i) => (
              <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls={`panel-${t.id}`}
                tabIndex={tab === t.id ? 0 : -1}
                onKeyDown={(e) => {
                  const n = TABS.length
                  const j = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n
                    : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : -1
                  if (j < 0) return
                  e.preventDefault()
                  setTab(TABS[j].id)
                  document.getElementById(`tab-${TABS[j].id}`)?.focus()
                }}
                onClick={() => setTab(t.id)}>{t.label}</button>
            ))}
          </div>
          <div className="panel" role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
            {tab === 'rozhodnuti' && <Comparison c={c} asOf={asOf} selected={shown?.id} onSelect={(id) => { setSelected(id); setTab('obchody') }} />}
            {tab === 'rozhodnuti' && <DecisionRecord c={c} />}
            {tab === 'obchody' && shown && <Trades c={c} a={shown} asOf={asOf} onPick={setSelected} />}
            {tab === 'portfolio' && <Portfolio c={c} asOf={asOf} />}
            {tab === 'strategie' && <Strategy c={c} />}
          </div>
        </>
      )}
      {c.status !== 'ok' && <Strategy c={c} />}
    </>
  )
}

function Decision({ c, asOf }: { c: ClientResult; asOf: string }) {
  // Everything below is rendered from engine output only: summary, decision record, reserve bridge, costs.
  const { stale, recalculating, result } = useApp()
  const step = nextStep(c)
  const rec = alt(c, c.recommended)
  const records = c.explanations ?? []
  const decisive = records.find((e) => e.code === 'decisive')
  const changed = records.filter((e) => e.section === 'sensitivity' && e.passed === false)
  const rate = (k: string) => pctTrim(Number(result?.assumptions[k] ?? 0) * 100)
  const b = c.reserve_bridge
  return (
    <section className="decision" style={{ ['--c' as string]: STATUS_COLOR[c.outcome.code] }} aria-labelledby="decision-h">
      <div>
        {stale[c.name] && <div className="stale-banner" role="status">Neaktuální: strategie v záložce Strategie obsahuje chybu. Zobrazen poslední platný výsledek.</div>}
        {recalculating && <div className="live" role="status">Přepočítávám…</div>}
        <div className="status"><span className="mark sq" style={{ ['--c' as string]: STATUS_COLOR[c.outcome.code] }} />{c.outcome.label}</div>
        <h2 id="decision-h" className="headline">{shortStep(c.summary, c.outcome.label)}</h2>
        {c.status !== 'ok' && (
          <ul>{c.issues.map((i, k) => <li key={k}>{[i.sheet, i.cell].filter(Boolean).join('!')} {i.message}</li>)}</ul>
        )}
        <p className="because"><b>Důvod:</b> {reason(c)}</p>
        {decisive && <p className="because">{explain(decisive)}</p>}
        {step.when && <p className="when">{step.whenType}: <b>{step.when}</b></p>}
        {changed.map((e, k) => <p key={k} className="stale">{explain(e)}</p>)}
        {rec && <Orders a={rec} asOf={asOf} />}
        {b && (
          <details className="record">
          <summary>Výpočet potřebné hotovosti</summary>
          <dl className="bridge" aria-label="Výpočet potřebné hotovosti">
            <dt>Známé výběry do {date(b.window_end)} ({c.reserve_days} dnů)</dt><dd>{czk(b.withdrawals)}</dd>
            <dt>Náklady převodu měn na nekrytou část ({rate('fx_cost')})</dt><dd>{czk(b.fx_allowance)}</dd>
            <dt className="sum">Rezerva na výběry</dt><dd className="sum">{czk(b.earmark)}</dd>
            <dt>Zbývající portfolio = majetek {czk(b.nav, 0)} − rezerva</dt><dd>{czk(b.investable)}</dd>
            <dt>Cílová hotovost {pctTrim(b.cash_target_pct)} ze zbývajícího portfolia</dt><dd>{czk(b.target_cash)}</dd>
            <dt className="sum">Potřebná hotovost celkem (dnes {czk(b.cash_today)})</dt><dd className="sum">{czk(b.required_cash)}</dd>
          </dl>
          <p className="muted" style={{ fontSize: '0.8rem', margin: '4px 0 0' }}>Částky jsou zaokrouhlené; součet se může lišit o 0,01 Kč.</p>
          </details>
        )}
        {c.status === 'ok' && <Meaning c={c} asOf={asOf} />}
      </div>
      {rec && c.recommended !== 'BASE' && (
        <div className="costs">
          <h3 style={{ marginBottom: 8 }}>Odhad nákladů</h3>
          <dl>
            <dt>Poplatky brokerovi</dt><dd>{czk(rec.commissions)}</dd>
            <dt>Převod měn ({rate('fx_cost')})</dt><dd>{czk(rec.fx_cost)}</dd>
            <dt>Odhad daně ({rate('tax_rate')})</dt><dd>{rec.tax === null ? 'nelze určit' : czk(rec.tax)}</dd>
            {rec.tax_high !== null && Number(rec.tax_high) > 0 && <><dt className="muted">při sazbě {rate('tax_rate_high')}</dt><dd className="muted">{czk(rec.tax_high)}</dd></>}
            {rec.tax === null && rec.tax_corporate !== null && <><dt className="muted">podmíněně {rate('corporate_tax_rate')} ze zisku</dt><dd className="muted">{czk(rec.tax_corporate)}</dd></>}
            <dt className="total">Celkem</dt><dd className="total">{czk(rec.total_cost)}</dd>
          </dl>
          <p className="muted" style={{ marginTop: 10, fontSize: '0.85rem' }}>
            {plural(rec.order_count, 'pokyn', 'pokyny', 'pokynů')}, objem {czk(rec.turnover, 0)}. Daň je modelový odhad, nesnižuje hotovost (platí se v přiznání).
          </p>
          <h3 style={{ margin: '16px 0 6px', fontSize: '0.95rem' }}>Před zadáním pokynů ověřit</h3>
          <ul className="checklist">
            <li>aktuální ceny, kurzy a hotovost (výpočet je k {date(asOf)}) – pak přepočítat</li>
            <li>termíny a částky vkladů a výběrů s klientem</li>
            {rec.orders.some((o) => o.side === 'SELL') && c.tax_regime === 'FO' && <li>u prodávaných lotů datum nabytí u brokera (časový test)</li>}
            <li>zda klientova smlouva nemá pevný limit přísnější než pásma strategie</li>
          </ul>
        </div>
      )}
    </section>
  )
}

// Bookkeeping of the search (variants generated, their raw results, ranking positions) and checks that passed are
// left out: the record shows what decided the outcome.
const ROUTINE = new Set(['generated', 'skipped', 'result', 'rank'])

function DecisionRecord({ c }: { c: ClientResult }) {
  const records = (c.explanations ?? []).filter((e) => !ROUTINE.has(e.code) && !(e.code === 'band_check' && e.passed))
  return (
    <details className="record-all">
      <summary><h2>Záznam rozhodnutí</h2> <span className="muted">kontroly, které rozhodly ({records.length})</span></summary>
      {SECTIONS.filter((sec) => sec.id !== 'decision' && records.some((e) => e.section === sec.id)).map((sec) => (
        <details key={sec.id} className="record">
          <summary>{sec.title}</summary>
          <ul>
            {records.filter((e) => e.section === sec.id).map((e, k) => (
              <li key={k}>
                {e.passed === true && <span className="tag good">splněno</span>}
                {e.passed === false && <span className="tag bad">nesplněno</span>} {explain(e)}
              </li>
            ))}
          </ul>
        </details>
      ))}
    </details>
  )
}

function Comparison({ c, asOf, selected, onSelect }: { c: ClientResult; asOf: string; selected?: string; onSelect: (id: string) => void }) {
  // recommended first, then by rank, infeasible/ineligible last; by default only the recommendation and its nearest competitor
  const { result } = useApp()
  const [all, setAll] = useState(false)
  const sorted = [...c.alternatives].sort((x, y) => (x.id === c.recommended ? -1 : y.id === c.recommended ? 1 : (x.rank ?? 99) - (y.rank ?? 99)))
  const alts = all ? sorted : sorted.slice(0, 2)
  const row = (label: string, f: (a: Alternative) => React.ReactNode) => (
    <tr>
      <th scope="row">{label}</th>
      {alts.map((a) => <td key={a.id} className={a.id === c.recommended ? 'rec n' : 'n'}>{f(a)}</td>)}
    </tr>
  )
  return (
    <>
      <h2>Porovnání variant</h2>
      <p className="lead">
        Doporučená varianta a nejbližší další. Všechny varianty se simulují stejnými pravidly do {date(c.horizon_end)}; pořadí:
        proveditelnost → dodržení pásem → náklady → počet pokynů → objem → dřívější termín. Kliknutím na název zobrazíte obchody.
      </p>
      {sorted.length > 2 && (
        <p><button className="btn" onClick={() => setAll(!all)} aria-expanded={all}>
          {all ? 'Zobrazit jen doporučenou a nejbližší variantu' : `Zobrazit všechny varianty (${sorted.length})`}
        </button></p>
      )}
      {all && <p className="scroll-hint">Další varianty jsou vpravo – tabulku lze posunout do strany.</p>}
      <div className="table-wrap">
        <table className="compare">
          <thead>
            <tr>
              <th scope="col">Varianta</th>
              {alts.map((a) => (
                <th key={a.id} scope="col" className={a.id === c.recommended ? 'rec' : ''} aria-sort="none">
                  <button onClick={() => onSelect(a.id)} aria-pressed={a.id === selected}>{ALT_NAMES[a.id]}</button>
                  <div>{a.id === c.recommended ? <span className="tag good">doporučeno</span> : a.rank ? <span className="tag">{a.rank}. v pořadí</span> : <span className="tag">nepřípustná</span>}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {row('Proveditelnost (hotovost ≥ 0 každý den)', (a) => a.feasible ? 'ano' : <span className="tag bad">ne – {String(a.infeasibility?.currency ?? "")} {date(a.infeasibility?.date as string)}</span>)}
            {row('Pásma dodržena po dokončení', (a) => a.compliant ? 'ano' : <span title="součet překročení pásem v nejhorším kontrolním bodě">ne, {pp(a.residual, 2, false)}</span>)}
            {row('Počet pokynů', (a) => a.order_count)}
            {row('Objem obchodů', (a) => czk(a.turnover, 0))}
            {row('Poplatky', (a) => czk(a.commissions))}
            {row('Převod měn', (a) => czk(a.fx_cost))}
            {row(taxCols(result?.assumptions), (a) => a.tax === null ? 'nelze určit' : <>{czk(a.tax)}<br /><span className="muted">{czk(a.tax_high)}</span></>)}
            {row('Celkem náklady', (a) => <b>{czk(a.total_cost)}</b>)}
            {row('Nejnižší hotovost celkem, všechny měny (datum)', (a) => <>{czk(a.min_cash)}<br /><span className="muted">{date(a.min_cash_date)}</span></>)}
            {row('Nejnižší zůstatek CZK (datum)', (a) => <>{czk(a.min_czk)}<br /><span className="muted">{date(a.min_czk_date)}</span></>)}
            {row('První obchod', (a) => date(a.first_order))}
            {row('Pozdější kroky', (a) => { const d = [...new Set(a.orders.filter((o) => o.trade_date > asOf).map((o) => `${date(o.trade_date)}${o.conditional ? ' (podmíněně)' : ''}`))]; return d.length ? d.join(', ') : '—' })}
            {row('Test čekání', (a) => a.wait_test ? (
              <span>
                {a.wait_test.passed ? <span className="tag good">splněn</span> : <span className="tag bad">nesplněn</span>}<br />
                {a.wait_test.days} / {a.wait_test.max_days} dní<br />
                odchylka {num(a.wait_test.max_deviation)} / {num(a.wait_test.deviation_cap, 0)} p. b.<br />
                úspora {a.wait_test.saving === null ? '—' : czk(a.wait_test.saving, 0)} / min. {czk(a.wait_test.min_saving, 0)}
              </span>
            ) : '—')}
          </tbody>
        </table>
      </div>
      {c.benchmark && c.benchmark.alternative !== c.recommended && (() => {
        const sr = alt(c, c.benchmark.alternative)!
        return (
          <p className="lead" style={{ marginTop: 12 }}>
            Jednoduché pravidlo (při překročení pásma hned vše na cíl, jinak nic) by zvolilo „{ALT_NAMES[sr.id]}“:
            {' '}{plural(sr.order_count, 'pokyn', 'pokyny', 'pokynů')}, náklady {czk(sr.total_cost, 0)}.
            {Number(c.benchmark.saving) > 0 ? <> Doporučení je levnější o <b>{czk(c.benchmark.saving, 0)}</b>.</> : <> Doporučení stojí o {czk(c.benchmark.saving.replace(/^-/, ''), 0)} víc – důvod je v pořadí výše.</>}
          </p>
        )
      })()}
      {c.alternatives.some((a) => a.residual_notes.length > 0 && a.id !== 'BASE' && a.id === c.recommended) && (
        <p className="stale">Doporučená varianta nedrží všechna pásma – manažer musí posoudit zbývající odchylky.</p>
      )}
    </>
  )
}

function Trades({ c, a, asOf, onPick }: { c: ClientResult; a: Alternative; asOf: string; onPick: (id: string) => void }) {
  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
        <h2 style={{ margin: 0 }}>Obchody: {ALT_NAMES[a.id]}</h2>
        <label className="no-print">
          <span className="visually-hidden">Varianta</span>
          <select value={a.id} onChange={(e) => onPick(e.target.value)} className="btn">
            {c.alternatives.map((x) => <option key={x.id} value={x.id}>{ALT_NAMES[x.id]}{x.id === c.recommended ? ' (doporučeno)' : ''}</option>)}
          </select>
        </label>
        <button className="btn no-print" onClick={() => window.print()}>Tisk zprávy</button>
      </div>
      {a.orders.length === 0 ? <p className="lead" style={{ marginTop: 12 }}>Varianta neobsahuje žádné obchody.</p> : (
        <>
          <p className="lead" style={{ marginTop: 12 }}>
            Kroky po {date(asOf)} jsou podmíněné: provedou se jen pokud nastane uvedená událost a po novém přepočtu.
            Ceny a kurzy jsou modelové (ze zadání).
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Obchod / vypořádání</th><th>Pokyn</th><th className="n">Kusy</th><th className="n">Cena</th>
                  <th className="n">Hrubě</th><th className="n">Poplatek</th><th>Důvod</th><th>Prodané loty</th>
                </tr>
              </thead>
              <tbody>
                {a.orders.map((o, k) => (
                  <tr key={k} className={o.conditional ? 'cond' : ''}>
                    <td>{date(o.trade_date)}<br /><span className="muted">vyp. {date(o.settlement_date)}</span></td>
                    <td><b>{o.side === 'BUY' ? 'Nákup' : 'Prodej'} {o.ticker}</b>{o.conditional ? <><br /><span className="tag">podmíněně – {STEP_REASON[o.step_reason]}</span></> : o.trade_date > asOf && <><br /><span className="tag">plánováno – {STEP_REASON[o.step_reason]}</span></>}</td>
                    <td className="n">{int(o.units)}</td>
                    <td className="n">{money(o.price, o.currency)}</td>
                    <td className="n">{money(o.gross, o.currency)}<br /><span className="muted">{czk(o.gross_czk)}</span></td>
                    <td className="n">{money(o.commission, o.currency)}<br /><span className="muted">{czk(o.commission_czk)}</span></td>
                    <td><Tags tags={o.tags} /></td>
                    <td>
                      {(o.lots ?? []).map((l, j) => (
                        <div key={j}>
                          {units(l.units)} z {date(l.acquired)}: {Number(l.gain) < 0 ? `ztráta ${czk(-Number(l.gain))}` : `zisk ${czk(l.gain)}`},{' '}
                          {l.exempt ? (l.first_exempt && l.first_exempt > asOf ? <span className="tag warn">osvobozeno od {date(l.first_exempt)} (předpoklad)</span> : <span className="tag good">osvobozeno</span>)
                            : c.tax_regime === 'FO' ? <span className="tag bad">zdanitelné</span> : <span className="tag">s.r.o.</span>}
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <details className="record-all">
      <summary><h2>Podrobnosti</h2> <span className="muted">hotovost po dnech, převody měn, kroky plánu</span></summary>
      {a.fx.length > 0 && (
        <>
          <h2>Převody měn</h2>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Provedení</th><th>K dispozici</th><th className="n">Prodáno</th><th className="n">Získáno</th><th className="n">Náklad</th><th>Účel</th></tr></thead>
              <tbody>
                {a.fx.map((f, k) => (
                  <tr key={k}>
                    <td>{date(f.executed)}</td><td>{date(f.available)}</td>
                    <td className="n">{money(f.source_amount, f.source)}</td><td className="n">{money(f.delivered, f.target)}</td>
                    <td className="n">{czk(f.cost_czk)}</td>
                    <td>{f.purpose === 'withdrawal' ? `výběr ${date(f.ref)}` : `nákup ${f.ref}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {a.steps.length > 0 && (
        <>
          <h2>Kroky plánu</h2>
          <p className="lead">Každý krok počítá s majetkem a rezervou k danému dni; základ = majetek − rezerva + známé budoucí vklady.</p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Datum</th><th>Krok</th><th className="n">Majetek</th><th className="n">Rezerva na výběry</th><th className="n">Základ pro velikost obchodů</th><th className="n">Doplněno hotovosti</th></tr></thead>
              <tbody>
                {a.steps.map((st, k) => (
                  <tr key={k}>
                    <td>{date(st.date)}</td>
                    <td>{st.kind === 'reserve' ? 'doplnění rezervy' : `rebalancování – ${STEP_REASON[st.reason] ?? st.reason}${st.mode === 'T' ? ' (na cíl)' : st.mode === 'P' ? ' (částečně)' : ''}`}</td>
                    <td className="n">{czk(st.nav)}</td><td className="n">{czk(st.earmark)}</td>
                    <td className="n">{st.basis === null ? '—' : czk(st.basis)}</td><td className="n">{st.amount === null ? '—' : czk(st.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <h2>Vypořádaná hotovost podle data valuty</h2>
      <p className="lead">Každý pohyb na účtu s datem valuty a zůstatkem dané měny po něm (prodeje T+2, převod měn +1 pracovní den).
        Tvrdé pravidlo: zůstatek nikdy pod nulou.</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Valuta</th><th>Měna</th><th>Pohyb</th><th className="n">Částka</th><th className="n">Zůstatek po pohybu</th></tr></thead>
          <tbody>
            {a.ledger.map((e, k) => (
              <tr key={k}>
                <td>{date(e.value_date)}{e.origin !== e.value_date && <span className="muted"> (obchod {date(e.origin)})</span>}</td>
                <td>{e.currency}</td>
                <td>{LEDGER_KIND(e.kind, e.ref, Number(e.amount))}</td>
                <td className="n">{money(e.amount, e.currency)}</td>
                <td className="n" style={Number(e.balance_after) < -0.005 ? { color: 'var(--s-fix)', fontWeight: 700 } : {}}>{money(e.balance_after, e.currency)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ marginTop: 10 }}>Odhad daně se do hotovosti nepromítá – platí se v daňovém přiznání.</p>
      </details>
    </>
  )
}

function Portfolio({ c, asOf }: { c: ClientResult; asOf: string }) {
  const { snapshot } = useApp()
  const v = c.valuation!
  const rec = alt(c, c.recommended)
  const pol = useApp().policies[c.name]
  return (
    <>
      <h2>Alokace a toleranční pásma</h2>
      <p className="lead">Váhy v % celkového majetku včetně hotovosti. Pásmo = užší z ±{pp(pol?.band_abs ?? 0, 2, false)} a ±{pct(pol?.band_rel ?? 0, 0)} cílové váhy (strategie klienta).</p>
      <GaugeLegend projected={Number(c.earmark_today ?? 0) > 0} after={!!rec && c.recommended !== 'BASE'} />
      <div>{gaugesFor(c, asOf, rec).map((g) => <BandGauge key={g.key} g={g} big />)}</div>
      <h2>Pozice</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Složka</th><th className="n">Kusy</th><th className="n">Hodnota</th><th className="n">Váha</th><th className="n">Cíl</th><th className="n">Odchylka</th><th className="n">Relativně</th><th className="n">Pásmo</th></tr></thead>
          <tbody>
            {[...v.components, v.equity].map((x) => (
              <tr key={x.key}>
                <td>{compName(x.key)}{x.breach && <> <span className="tag bad">mimo pásmo</span></>}</td>
                <td className="n">{x.units === null ? '' : int(x.units)}</td>
                <td className="n">{czk(x.value)}</td>
                <td className="n">{pct(x.weight)}</td>
                <td className="n">{pctTrim(x.target)}</td>
                <td className="n">{pp(x.deviation)}</td>
                <td className="n">{x.relative_deviation === null ? (x.key === 'EQ' ? '' : '— (cíl 0 %)') : pct(x.relative_deviation, 1)}</td>
                <td className="n">{pct(x.band_low, 2)}–{pct(x.band_high, 2)}</td>
              </tr>
            ))}
            <tr><td><b>Majetek celkem</b></td><td /><td className="n"><b>{czk(v.nav)}</b></td><td className="n">{pct(100, 2)}</td><td colSpan={4} /></tr>
          </tbody>
        </table>
      </div>
      <h2>Hotovost podle měny</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Měna</th><th className="n">Zůstatek</th><th className="n">V Kč</th></tr></thead>
          <tbody>{v.cash.map((x) => <tr key={x.currency}><td>{x.currency}</td><td className="n">{money(x.amount, x.currency)}</td><td className="n">{czk(x.value_czk)}</td></tr>)}</tbody>
        </table>
      </div>
      <h2>Daňové loty</h2>
      <p className="lead">Nákupní cena přepočtena dnešním kurzem (zjednodušení povolené zadáním). Časový test: 3 roky od nabytí (= vypořádání nákupu, předpoklad).</p>
      <div className="table-wrap">
        <table>
          <thead><tr><th>Instrument</th><th>Nákup</th><th className="n">Kusy</th><th className="n">Nákupní cena</th><th className="n">Tržní hodnota</th><th className="n">Nerealizovaný zisk</th><th className="n">Drženo dní</th><th>Daňový stav</th></tr></thead>
          <tbody>
            {v.lots.map((l, k) => (
              <tr key={k}>
                <td>{l.ticker}</td><td>{date(l.acquired)}</td><td className="n">{int(l.units)}</td><td className="n">{money(l.buy_price, snapshot?.dataset.instruments.find((i) => i.ticker === l.ticker)?.currency ?? '')}</td>
                <td className="n">{czk(l.market_value)}</td><td className="n">{czk(l.unrealised_gain)}</td><td className="n">{int(l.holding_days)}</td>
                <td>{TAX_STATUS[l.tax_status]}{l.first_exempt && l.tax_status !== 'exempt' && <> – osvobození od {date(l.first_exempt)}{l.tax_status === 'pending' && ' (předpoklad)'}</>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2>Vklady, výběry a termíny</h2>
      {v.flows.length === 0 ? <p className="lead">Klient nemá plánované vklady ani výběry.</p> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Datum</th><th>Den valuty</th><th>Typ</th><th className="n">Částka</th><th>Poznámka</th></tr></thead>
            <tbody>
              {v.flows.map((f, k) => (
                <tr key={k} className={f.past ? 'cond' : ''}>
                  <td>{date(f.date)} <span className="muted">({weekday(f.date)})</span></td>
                  <td>{date(f.value_date)}{!f.in_horizon && !f.past && <span className="muted"> – mimo horizont</span>}{f.past && <span className="muted"> – minulý, ignorován</span>}</td>
                  <td>{f.kind || (Number(f.amount) > 0 ? 'Vklad' : 'Výběr')}</td>
                  <td className="n">{czk(f.amount)}</td><td>{f.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
