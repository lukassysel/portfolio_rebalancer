// Monthly import (doc 09 §5): upload → validation report → explicit „Použít“ activates the whole snapshot or nothing.
import { useEffect, useRef, useState } from 'react'
import { ApiError } from '../api/client'
import type { Dataset, EvaluationResult, Issue, Snapshot } from '../api/types'
import { since } from './Meaning'
import { compName } from '../texts'
import { useApp } from '../state'
import { date, int, num } from '../format'

const where = (i: Issue) => [i.sheet, i.cell].filter(Boolean).join('!')

// What changed between the current and the staged dataset, per client (inputs only; nothing is computed),
// and how the evaluation moved: components newly outside / still outside / back inside their band.
function changes(prev: Dataset, next: Dataset, before?: EvaluationResult | null, after?: EvaluationResult | null): string[] {
  const out: string[] = []
  const prices = next.instruments.flatMap((i) => {
    const p = prev.instruments.find((x) => x.ticker === i.ticker)
    return p && p.price !== i.price ? [`${i.ticker} ${num(p.price)} → ${num(i.price)} ${i.currency}`] : []
  })
  const fx = Object.keys(next.fx).filter((k) => prev.fx[k] !== undefined && prev.fx[k] !== next.fx[k])
    .map((k) => `${k}/CZK ${num(prev.fx[k], 3)} → ${num(next.fx[k], 3)}`)
  if (prices.length || fx.length) out.push(`Ceny a kurzy: ${[...prices, ...fx].join('; ')}`)
  const old = new Map(prev.clients.map((c) => [c.name, c]))
  for (const c of next.clients) {
    const p = old.get(c.name)
    if (!p) { out.push(`${c.name}: nový klient`); continue }
    const units = (cl: typeof c) => {
      const m: Record<string, number> = {}
      for (const l of cl.lots ?? []) m[l.ticker] = (m[l.ticker] ?? 0) + l.units
      return m
    }
    const ub = units(p), ua = units(c)
    const tick = [...new Set([...Object.keys(ub), ...Object.keys(ua)])].filter((t) => (ub[t] ?? 0) !== (ua[t] ?? 0))
    const parts = tick.map((t) => `${t} ${int(ub[t] ?? 0)} → ${int(ua[t] ?? 0)} ks`)
    const cash = (cl: typeof c) => (cl.cash ?? []).map((x) => `${x.amount} ${x.currency}`).sort().join(', ')
    if (cash(p) !== cash(c)) parts.push('hotovost změněna')
    const flows = (cl: typeof c) => (cl.flows ?? []).map((f) => `${f.date}:${f.amount}`).sort().join('|')
    if (flows(p) !== flows(c)) parts.push('plánované toky změněny')
    if (JSON.stringify(p.targets) !== JSON.stringify(c.targets)) parts.push('cílové váhy změněny')
    let line = `${c.name}: ${parts.length ? parts.join('; ') : 'beze změny pozic, hotovosti, toků i cílů'}`
    const r0 = before?.clients.find((x) => x.name === c.name)
    const r1 = after?.clients.find((x) => x.name === c.name)
    if (r0 && r1 && r0.status === 'ok' && r1.status === 'ok') {
      const d = since(r0, before!.valuation_date, r1, after!.valuation_date)
      const names = (ks: string[]) => ks.map(compName).join(', ')
      const res = [
        d.outcome && `výsledek ${d.outcome}`,
        d.added.length && `nově mimo pásmo ${names(d.added)}`,
        d.kept.length && `stále mimo pásmo ${names(d.kept)}`,
        d.gone.length && `zpět v pásmu ${names(d.gone)}`,
      ].filter(Boolean)
      if (res.length) line += ` → ${res.join('; ')}`
      if (d.added.length) line += parts.length
        ? ' (změnily se i vstupy klienta – příčinu posoudit)'
        : ' (vstupy klienta beze změny – odchylku způsobil pohyb cen a kurzů)'
    }
    out.push(line)
  }
  for (const n of old.keys()) if (!next.clients.some((c) => c.name === n)) out.push(`${n}: v novém souboru chybí`)
  return out
}

export function ImportDialog({ onClose }: { onClose: () => void }) {
  const { importFile, activate, snapshot, policies, result } = useApp()
  const edited = snapshot ? Object.keys(policies).filter((n) => JSON.stringify(policies[n]) !== JSON.stringify(snapshot.policies[n])) : []
  const [keep, setKeep] = useState<Record<string, boolean>>({})
  const ref = useRef<HTMLDialogElement>(null)
  const [busy, setBusy] = useState(false)
  const [staged, setStaged] = useState<Snapshot | null>(null)
  const [errors, setErrors] = useState<Issue[] | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    ref.current?.showModal()
  }, [])

  async function onFile(f: File | undefined) {
    if (!f) return
    setBusy(true)
    setStaged(null)
    setErrors(null)
    setMessage(null)
    try {
      setStaged(await importFile(f))
    } catch (e) {
      const err = e as ApiError
      setMessage(err.message)
      setErrors(err.issues ?? [])
    } finally {
      setBusy(false)
    }
  }

  const prev = snapshot?.dataset
  const clientErrors = staged?.issues.filter((i) => i.severity === 'error') ?? []
  const warnings = staged?.issues.filter((i) => i.severity === 'warning') ?? []

  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="import-title">
      <div className="dialog-body">
        <h2 id="import-title">Načíst data (Excel)</h2>
        <p className="muted">
          Sešit .xlsx ve formátu zadání (listy Instrumenty, Kurzy, Klienti, Pozice, Hotovost, Cash flow; volitelně Strategie). Stejný formát vytvoří tlačítko „Uložit data (Excel)“ – takto se pokračuje v uložené práci nebo se načtou nové ceny a pozice na další měsíc.
          Soubor musí obsahovat skutečný stav účtů – minulé návrhy se nepovažují za provedené.
        </p>
        <label className="btn">
          Vybrat soubor
          <input className="visually-hidden" type="file" accept=".xlsx" onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
        {busy && <p role="status">Kontroluji soubor…</p>}
        {message && (
          <div role="alert">
            <p><b>{message}</b> Současná data zůstávají beze změny.</p>
            <ul className="issues">
              {errors?.map((i, k) => (
                <li key={k}>{where(i) && <b>{where(i)}: </b>}{i.message}</li>
              ))}
            </ul>
          </div>
        )}
        {staged && (
          <div>
            <h3 style={{ marginTop: 16 }}>Kontrola souboru</h3>
            <ul className="issues">
              <li>Datum ocenění: <b>{date(staged.dataset.valuation_date)}</b>{prev && prev.valuation_date !== staged.dataset.valuation_date && ` (dosud ${date(prev.valuation_date)})`}</li>
              <li>Klienti: {staged.dataset.clients.map((c) => c.name).join(', ')}</li>
              {prev && changes(prev, staged.dataset, result, staged.result).map((t, k) => <li key={`c${k}`}>{t}</li>)}
              {clientErrors.map((i, k) => (
                <li key={`e${k}`}><span className="tag bad">chyba</span> {i.client}: {where(i) && <b>{where(i)} </b>}{i.message} – klient bude označen „Opravit data“.</li>
              ))}
              {warnings.map((i, k) => (
                <li key={`w${k}`}><span className="tag warn">upozornění</span> {i.client ? `${i.client}: ` : ''}{where(i) && <b>{where(i)} </b>}{i.message}</li>
              ))}
            </ul>
            {edited.filter((n) => staged.dataset.clients.some((c) => c.name === n)).length > 0 ? (
              <fieldset style={{ border: 0, padding: 0 }}>
                <legend><b>Upravené strategie</b> – ponechat i pro nová data? (cílové váhy se vezmou ze souboru)</legend>
                {edited.filter((n) => staged.dataset.clients.some((c) => c.name === n)).map((n) => (
                  <label key={n} style={{ display: 'block' }}>
                    <input type="checkbox" checked={keep[n] ?? true} onChange={(e) => setKeep({ ...keep, [n]: e.target.checked })} /> {n}
                  </label>
                ))}
              </fieldset>
            ) : <p className="muted">Strategie se načtou z listu „Strategie“; klienti bez něj dostanou výchozí strategii s cílovými vahami ze souboru.</p>}
          </div>
        )}
      </div>
      <div className="dialog-actions">
        <button className="btn" onClick={() => ref.current?.close()}>Zrušit</button>
        <button className="btn primary" disabled={!staged} onClick={() => {
          if (!staged) return
          const kept = Object.fromEntries(edited.filter((n) => keep[n] ?? true).map((n) => [n, policies[n]]))
          activate(staged, kept)
          ref.current?.close()
        }}>
          Použít data
        </button>
      </div>
    </dialog>
  )
}
