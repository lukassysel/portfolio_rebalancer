// Create or edit a client: profile, tax regime, target weights, positions (lots), cash and planned flows.
// The form only collects facts; the engine validates them and computes everything on save.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { getMeta } from '../api/client'
import type { Meta, Policy } from '../api/types'
import { num } from '../format'
import { useApp } from '../state'

type LotRow = { ticker: string; acquired: string; units: string; buy_price: string }
type CashRow = { currency: string; amount: string }
type FlowRow = { date: string; amount: string; note: string }
type Form = {
  name: string; profile: string; tax_regime: string; note: string
  targets: Record<string, string>; lots: LotRow[]; cash: CashRow[]; flows: FlowRow[]
}

const parse = (s: string) => s.trim().replace(/\s/g, '').replace(',', '.')
const isNum = (s: string) => /^-?\d+(\.\d+)?$/.test(parse(s))
const show = (v: unknown) => (v === null || v === undefined ? '' : String(v).replace('.', ','))

export function ClientEditor() {
  const { name: param } = useParams()
  const editing = param ? decodeURIComponent(param) : null
  const { snapshot, policies, updateBook } = useApp()
  const navigate = useNavigate()
  const [meta, setMeta] = useState<Meta | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const confirmRef = useRef<HTMLDialogElement>(null)
  useEffect(() => { getMeta().then(setMeta).catch(() => undefined) }, [])

  const ds = snapshot?.dataset
  const tickers = useMemo(() => ds?.instruments.map((i) => i.ticker) ?? [], [ds])
  const currencies = useMemo(() => Object.keys(ds?.fx ?? { CZK: '1' }), [ds])
  const existing = ds?.clients.find((c) => c.name === editing)

  const [f, setF] = useState<Form>(() => ({
    name: existing?.name ?? '', profile: existing?.profile ?? '', tax_regime: existing?.tax_regime ?? 'FO',
    note: existing?.note ?? '',
    targets: Object.fromEntries([...tickers, 'CASH'].map((k) => [k, show((editing && policies[editing]?.targets[k]) ?? existing?.targets[k] ?? '0')])),
    lots: (existing?.lots ?? []).map((l) => ({ ticker: l.ticker, acquired: l.acquired, units: String(l.units), buy_price: show(l.buy_price) })),
    cash: (existing?.cash ?? [{ currency: 'CZK', amount: '0' }]).map((c) => ({ currency: c.currency, amount: show(c.amount) })),
    flows: (existing?.flows ?? []).map((x) => ({ date: x.date, amount: show(x.amount), note: x.note ?? '' })),
  }))

  const errors = useMemo(() => {
    const e: string[] = []
    const name = f.name.trim()
    if (!name) e.push('Zadejte jméno klienta.')
    if (ds?.clients.some((c) => c.name === name && c.name !== editing)) e.push(`Klient „${name}“ už existuje.`)
    let sum = 0
    for (const [k, v] of Object.entries(f.targets)) {
      if (!isNum(v) || Number(parse(v)) < 0 || Number(parse(v)) > 100) e.push(`Cílová váha ${k === 'CASH' ? 'hotovosti' : k}: číslo 0–100.`)
      else sum += Number(parse(v))
    }
    if (Math.abs(sum - 100) > 1e-9) e.push(`Součet cílových vah je ${num(sum)} %, musí být 100 %.`)
    f.lots.forEach((l, i) => {
      if (!l.acquired) e.push(`Pozice ${i + 1}: chybí datum nákupu.`)
      if (!/^\d+$/.test(parse(l.units)) || Number(parse(l.units)) <= 0) e.push(`Pozice ${i + 1}: počet kusů musí být kladné celé číslo.`)
      if (!isNum(l.buy_price) || Number(parse(l.buy_price)) <= 0) e.push(`Pozice ${i + 1}: neplatná nákupní cena.`)
    })
    const seen = new Set<string>()
    f.cash.forEach((c, i) => {
      if (!isNum(c.amount) || Number(parse(c.amount)) < 0) e.push(`Hotovost ${i + 1}: zůstatek musí být nezáporné číslo.`)
      if (seen.has(c.currency)) e.push(`Hotovost: měna ${c.currency} je uvedena dvakrát.`)
      seen.add(c.currency)
    })
    f.flows.forEach((x, i) => {
      if (!x.date) e.push(`Tok ${i + 1}: chybí datum.`)
      if (!isNum(x.amount) || Number(parse(x.amount)) === 0) e.push(`Tok ${i + 1}: částka musí být nenulové číslo (+ vklad, − výběr).`)
    })
    return e
  }, [f, ds, editing])

  if (!snapshot || !ds) return null
  if (editing && !existing) return <p>Klient „{editing}“ v datech není. <Link to="/">Zpět na přehled</Link></p>

  const set = (patch: Partial<Form>) => setF((cur) => ({ ...cur, ...patch }))
  const setRow = <K extends 'lots' | 'cash' | 'flows'>(key: K, i: number, patch: Partial<Form[K][number]>) =>
    setF((cur) => ({ ...cur, [key]: cur[key].map((r, j) => (j === i ? { ...r, ...patch } : r)) }))
  const removeRow = (key: 'lots' | 'cash' | 'flows', i: number) =>
    setF((cur) => ({ ...cur, [key]: cur[key].filter((_, j) => j !== i) }))

  function save() {
    setSubmitted(true)
    if (errors.length || !ds || !snapshot) return
    const name = f.name.trim()
    const targets = Object.fromEntries(Object.entries(f.targets).map(([k, v]) => [k, parse(v)]))
    const client = {
      name, profile: f.profile.trim(), tax_regime: f.tax_regime, note: f.note.trim(), targets,
      lots: f.lots.map((l) => ({ ticker: l.ticker, acquired: l.acquired, units: Number(parse(l.units)), buy_price: parse(l.buy_price) })),
      cash: f.cash.map((c) => ({ currency: c.currency, amount: parse(c.amount) })),
      flows: f.flows.map((x) => ({
        date: x.date, amount: parse(x.amount), kind: Number(parse(x.amount)) > 0 ? 'Vklad' : 'Výběr', note: x.note.trim(),
      })),
    }
    const clients = editing ? ds.clients.map((c) => (c.name === editing ? client : c)) : [...ds.clients, client]
    const base: Policy = (editing && policies[editing]) || (meta?.default_policy as Policy)
    const nextPolicies = { ...policies }
    const nextDefaults = { ...snapshot.policies }
    if (editing && editing !== name) { delete nextPolicies[editing]; delete nextDefaults[editing] }
    nextPolicies[name] = { ...base, targets }
    nextDefaults[name] = { ...((editing && snapshot.policies[editing]) || (meta?.default_policy as Policy)), targets }
    const source = ds.source.endsWith('(upraveno v aplikaci)') ? ds.source : `${ds.source} (upraveno v aplikaci)`
    updateBook({ ...ds, source, clients }, nextPolicies, nextDefaults,
      editing ? `Údaje klienta ${name} uloženy a přepočteny.` : `Klient ${name} přidán a vyhodnocen.`)
    navigate(`/klient/${encodeURIComponent(name)}`)
  }

  function remove() {
    if (!editing || !ds || !snapshot) return
    const nextPolicies = { ...policies }
    const nextDefaults = { ...snapshot.policies }
    delete nextPolicies[editing]
    delete nextDefaults[editing]
    updateBook({ ...ds, clients: ds.clients.filter((c) => c.name !== editing) }, nextPolicies, nextDefaults,
      `Klient ${editing} odebrán.`)
    navigate('/')
  }

  const inst = (t: string) => ds.instruments.find((i) => i.ticker === t)
  return (
    <div className="editor">
      <nav className="crumbs" aria-label="Drobečková navigace"><Link to="/">Přehled</Link> / {editing ? `Upravit: ${editing}` : 'Nový klient'}</nav>
      <h1>{editing ? `Upravit klienta ${editing}` : 'Nový klient'}</h1>
      <p className="lead">
        Zadejte skutečný stav účtu k datu ocenění {ds.valuation_date.split('-').reverse().map(Number).join('. ')} a cílové
        rozložení. Doporučení spočítá engine po uložení. Data se drží jen v tomto prohlížeči – pro uložení použijte
        „Uložit data (Excel)“ na přehledu.
      </p>

      <section className="ed-section">
        <h2>Základní údaje</h2>
        <div className="ed-grid">
          <label>Jméno klienta<input value={f.name} onChange={(e) => set({ name: e.target.value })} /></label>
          <label>Daňový režim
            <select value={f.tax_regime} onChange={(e) => set({ tax_regime: e.target.value })}>
              <option value="FO">fyzická osoba (FO)</option><option value="s.r.o.">právnická osoba (s.r.o.)</option>
            </select>
          </label>
          <label>Profil<input value={f.profile} onChange={(e) => set({ profile: e.target.value })} /></label>
          <label>Poznámka<input value={f.note} onChange={(e) => set({ note: e.target.value })} /></label>
        </div>
      </section>

      <section className="ed-section">
        <h2>Cílové rozložení (% celkového majetku vč. hotovosti)</h2>
        <div className="ed-grid targets">
          {[...tickers, 'CASH'].map((k) => (
            <label key={k}>{k === 'CASH' ? 'Hotovost' : `${k} (${inst(k)?.asset_class ?? ''})`}
              <input inputMode="decimal" value={f.targets[k] ?? ''} onChange={(e) => set({ targets: { ...f.targets, [k]: e.target.value } })} />
            </label>
          ))}
        </div>
      </section>

      <section className="ed-section">
        <h2>Pozice (jednotlivé nákupy)</h2>
        <table className="ed-table">
          <thead><tr><th>Instrument</th><th>Datum nákupu</th><th>Počet kusů</th><th>Nákupní cena (v měně instrumentu)</th><th /></tr></thead>
          <tbody>
            {f.lots.map((l, i) => (
              <tr key={i}>
                <td><select aria-label="Instrument" value={l.ticker} onChange={(e) => setRow('lots', i, { ticker: e.target.value })}>
                  {tickers.map((t) => <option key={t} value={t}>{t}</option>)}</select></td>
                <td><input aria-label="Datum nákupu" type="date" max={ds.valuation_date} value={l.acquired} onChange={(e) => setRow('lots', i, { acquired: e.target.value })} /></td>
                <td><input aria-label="Počet kusů" inputMode="numeric" value={l.units} onChange={(e) => setRow('lots', i, { units: e.target.value })} /></td>
                <td><input aria-label="Nákupní cena" inputMode="decimal" value={l.buy_price} onChange={(e) => setRow('lots', i, { buy_price: e.target.value })} /> {inst(l.ticker)?.currency}</td>
                <td><button className="btn" onClick={() => removeRow('lots', i)}>Odebrat</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn" onClick={() => set({ lots: [...f.lots, { ticker: tickers[0], acquired: '', units: '', buy_price: '' }] })}>Přidat pozici</button>
      </section>

      <section className="ed-section">
        <h2>Hotovost</h2>
        <table className="ed-table">
          <thead><tr><th>Měna</th><th>Zůstatek</th><th /></tr></thead>
          <tbody>
            {f.cash.map((c, i) => (
              <tr key={i}>
                <td><select aria-label="Měna" value={c.currency} onChange={(e) => setRow('cash', i, { currency: e.target.value })}>
                  {currencies.map((x) => <option key={x} value={x}>{x}</option>)}</select></td>
                <td><input aria-label="Zůstatek" inputMode="decimal" value={c.amount} onChange={(e) => setRow('cash', i, { amount: e.target.value })} /></td>
                <td><button className="btn" onClick={() => removeRow('cash', i)}>Odebrat</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn" onClick={() => set({ cash: [...f.cash, { currency: currencies.find((x) => !f.cash.some((c) => c.currency === x)) ?? 'CZK', amount: '0' }] })}>Přidat měnu</button>
      </section>

      <section className="ed-section">
        <h2>Plánované vklady a výběry (Kč)</h2>
        <p className="muted">Kladná částka = vklad, záporná = výběr.</p>
        <table className="ed-table">
          <thead><tr><th>Datum</th><th>Částka</th><th>Poznámka</th><th /></tr></thead>
          <tbody>
            {f.flows.map((x, i) => (
              <tr key={i}>
                <td><input aria-label="Datum toku" type="date" value={x.date} onChange={(e) => setRow('flows', i, { date: e.target.value })} /></td>
                <td><input aria-label="Částka" inputMode="decimal" value={x.amount} onChange={(e) => setRow('flows', i, { amount: e.target.value })} /></td>
                <td><input aria-label="Poznámka" value={x.note} onChange={(e) => setRow('flows', i, { note: e.target.value })} /></td>
                <td><button className="btn" onClick={() => removeRow('flows', i)}>Odebrat</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        <button className="btn" onClick={() => set({ flows: [...f.flows, { date: '', amount: '', note: '' }] })}>Přidat tok</button>
      </section>

      {submitted && errors.length > 0 && (
        <div className="notice error" role="alert"><ul>{errors.map((e, k) => <li key={k}>{e}</li>)}</ul></div>
      )}
      <div className="ed-actions">
        <button className="btn primary" onClick={save} disabled={!meta}>{editing ? 'Uložit a přepočítat' : 'Přidat klienta a vyhodnotit'}</button>
        <Link className="btn" to={editing ? `/klient/${encodeURIComponent(editing)}` : '/'}>Zrušit</Link>
        {editing && <button className="btn" onClick={() => confirmRef.current?.showModal()}>Odebrat klienta</button>}
      </div>
      <p className="muted">Parametry strategie (tolerance, minimální obchod, čekání) nastavíte po uložení v záložce Strategie.</p>
      <dialog ref={confirmRef} aria-labelledby="del-title">
        <div className="dialog-body"><h2 id="del-title">Odebrat klienta {editing}?</h2><p>Klient zmizí z přehledu. Uložený Excel se nemění.</p></div>
        <div className="dialog-actions">
          <button className="btn" onClick={() => confirmRef.current?.close()}>Ponechat</button>
          <button className="btn primary" onClick={() => { confirmRef.current?.close(); remove() }}>Odebrat klienta</button>
        </div>
      </dialog>
    </div>
  )
}
