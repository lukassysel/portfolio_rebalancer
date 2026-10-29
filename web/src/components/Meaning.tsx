// What a deviation means and what the rules add over a simple rule. Every number comes from the engine
// (triggers with band excess, stress, benchmark); the wording is fixed templates here.
import { Link } from 'react-router-dom'
import type { ClientResult, EvaluationResult } from '../api/types'
import { czk, date, pct, pctTrim, plural, pp } from '../format'
import { ALT_NAMES, alt, compName } from '../texts'

type Trigger = ClientResult['triggers'][number]

/** Today's band breaches, one per component: the total-asset view (A) wins, else the view after the reserve. */
export function todaysBreaches(c: ClientResult, asOf: string): Trigger[] {
  const today = c.triggers.filter((t) => t.date === asOf && t.excess !== null && t.excess !== undefined)
  const out: Trigger[] = []
  for (const t of today) {
    if (out.some((o) => o.scope === t.scope)) continue
    out.push(today.find((x) => x.scope === t.scope && x.measure === 'A') ?? t)
  }
  return out
}

function line(t: Trigger) {
  const reserve = t.measure !== 'A'
  const where = reserve ? ' po odečtení rezervy na výběry' : ''
  if (t.rule === 'T3') {
    return <>Nevyužitá hotovost{where}: {pct(t.deviation)} majetku při toleranci {pctTrim(t.band)}, tedy o <b>{pp(t.excess, 2, false)}</b> víc
      (asi <b>{czk(t.excess_czk, 0)}</b> leží neinvestovaných).</>
  }
  const up = Number(t.deviation) > 0
  return <>{compName(t.scope)}{where}: o {pp(t.deviation, 2, false)} {up ? 'nad' : 'pod'} cílem, z toho o <b>{pp(t.excess, 2, false)}</b>
    {up ? ' nad horní' : ' pod dolní'} hranicí pásma – asi <b>{czk(t.excess_czk, 0)}</b> {up ? 'navíc' : 'chybí'}.</>
}

/** One sentence per kind of problem; only what the numbers above show. */
function meaning(ts: Trigger[]): string[] {
  const out: string[] = []
  const eq = ts.find((t) => t.scope === 'EQ')
  if (eq) out.push(Number(eq.deviation) > 0
    ? 'Akcií je víc, než strategie dovoluje: portfolio je citlivější na pokles akciových trhů.'
    : 'Akcií je méně, než strategie předpokládá: portfolio se méně podílí na růstu, který si klient zvolil.')
  const cash = ts.find((t) => t.scope === 'CASH')
  if (cash?.rule === 'T3') out.push('Peníze bez investice nevydělávají podle strategie klienta.')
  else if (cash && Number(cash.deviation) < 0) out.push('Hotovost nestačí na plánované výběry – bez prodeje by na ně nebyly peníze.')
  if (ts.some((t) => t.measure !== 'A') && !ts.some((t) => t.measure === 'A' && t.scope !== 'CASH'))
    out.push('Z celého majetku to vypadá v pořádku; problém je vidět až po odečtení peněz, které klient brzy vybere.')
  return out
}

export function Meaning({ c, asOf }: { c: ClientResult; asOf: string }) {
  const ts = todaysBreaches(c, asOf)
  const s = c.stress
  if (!ts.length && !s) return null
  return (
    <div className="meaning">
      <h3>Co odchylka znamená</h3>
      {ts.length > 0 ? (
        <ul>{ts.map((t) => <li key={t.scope}>{line(t)}</li>)}</ul>
      ) : <p>Všechny složky jsou v pásmu, žádné pravidlo zásah nevyžaduje.</p>}
      {meaning(ts).map((m, k) => <p key={k}>{m}</p>)}
      {s && <Stress c={c} />}
    </div>
  )
}

export function Stress({ c }: { c: ClientResult }) {
  const s = c.stress!
  const more = Number(s.loss_pct) > Number(s.target_pct)
  return (
    <p className="stress">
      Kdyby akcie klesly o {pctTrim(s.drop)}, portfolio ztratí asi <b>{czk(s.loss, 0)}</b> ({pct(s.loss_pct)} majetku);
      při cílové alokaci by to bylo {czk(s.target_loss, 0)} ({pct(s.target_pct)}){Number(s.loss_pct) === Number(s.target_pct) ? '' : more ? ' – riziko je vyšší, než klient zvolil' : ' – riziko je nižší, než klient zvolil'}.
      {s.after_pct !== null && s.after_pct !== undefined && <> Po doporučeném plánu ({date(s.after_date)}) {pct(s.after_pct)} majetku.</>}
      <span className="muted"> Ilustrace citlivosti, ne předpověď.</span>
    </p>
  )
}

/** Short wording of what the recommendation does differently from the simple rule (fixed templates). */
function difference(c: ClientResult, asOf: string): string {
  const b = c.benchmark!
  const rec = alt(c, c.recommended)
  if (!rec) return ''
  if (b.alternative === c.recommended) return 'stejný výsledek'
  const out: string[] = []
  if (rec.kind === 'wait_tax' && rec.wait_test)
    out.push(`počká na osvobození od daně do ${date(rec.wait_date)}; do té doby odchylka nejvýš ${pp(rec.wait_test.max_deviation, 2, false)}`)
  else if (rec.kind === 'base') out.push('neobchoduje')
  if (rec.mode === 'P') out.push('vrací složky na okraj pásma, ne až na cíl')
  const hidden = todaysBreaches(c, asOf).filter((t) => t.measure !== 'A' && !c.valuation?.components.find((x) => x.key === t.scope)?.breach && t.scope !== 'CASH')
  if (hidden.length) out.push(`${hidden.map((t) => compName(t.scope)).join(' a ')} ${hidden.length > 1 ? 'jsou' : 'je'} mimo pásmo jen po odečtení rezervy na výběry`)
  return out.join('; ')
}

export function SimpleRule({ result }: { result: EvaluationResult }) {
  const asOf = result.valuation_date
  const rows = result.clients.filter((c) => c.benchmark)
  const tot = result.benchmark
  if (!rows.length || !tot) return null
  return (
    <section className="simple-rule" aria-labelledby="simple-h">
      <h2 id="simple-h">Co pravidla přinášejí oproti jednoduchému pravidlu</h2>
      <p className="lead">
        Jednoduché pravidlo: když je dnes některá složka mimo pásmo, vrátit hned všechno na cíl; jinak nic. Počítá se stejným
        výpočtem (ceny, poplatky, daně, hotovost i rezerva na výběry) – liší se jen rozhodnutím. Jde o modelové náklady, ne zaručenou úsporu.
      </p>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Klient</th><th>Jednoduché pravidlo</th><th className="n">Náklady</th><th>Doporučení</th><th className="n">Náklady</th>
              <th className="n">Rozdíl</th><th>V čem se liší</th></tr>
          </thead>
          <tbody>
            {rows.map((c) => {
              const s = alt(c, c.benchmark!.alternative)!
              const r = alt(c, c.recommended)!
              return (
                <tr key={c.name}>
                  <td><Link to={`/klient/${encodeURIComponent(c.name)}`}>{c.name}</Link></td>
                  <td>{ALT_NAMES[s.id]}{s.order_count > 0 && <>, {plural(s.order_count, 'pokyn', 'pokyny', 'pokynů')}</>}</td>
                  <td className="n">{czk(s.total_cost, 0)}</td>
                  <td>{ALT_NAMES[r.id]}{r.order_count > 0 && <>, {plural(r.order_count, 'pokyn', 'pokyny', 'pokynů')}</>}</td>
                  <td className="n">{czk(r.total_cost, 0)}</td>
                  <td className="n">{Number(c.benchmark!.saving) === 0 ? '—' : <b>{czk(c.benchmark!.saving, 0)}</b>}</td>
                  <td>{difference(c, asOf)}</td>
                </tr>
              )
            })}
            <tr className="total">
              <td>Celkem</td><td>{plural(tot.simple_orders, 'pokyn', 'pokyny', 'pokynů')}</td><td className="n">{czk(tot.simple_cost, 0)}</td>
              <td>{plural(tot.recommended_orders, 'pokyn', 'pokyny', 'pokynů')}</td><td className="n">{czk(tot.recommended_cost, 0)}</td>
              <td className="n"><b>{czk(tot.saving, 0)}</b></td><td />
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  )
}

/** Components outside their band today (any view), for month-to-month comparison. */
export const outside = (c: ClientResult | undefined, asOf: string | undefined) =>
  new Set(c && asOf ? todaysBreaches(c, asOf).map((t) => t.scope) : [])

/** New / persisting / resolved breaches between two evaluations of the same client. */
export function since(prev: ClientResult | undefined, prevAsOf: string | undefined, cur: ClientResult, asOf: string) {
  const a = outside(prev, prevAsOf)
  const b = outside(cur, asOf)
  return {
    known: !!prev,
    added: [...b].filter((k) => !a.has(k)),
    kept: [...b].filter((k) => a.has(k)),
    gone: [...a].filter((k) => !b.has(k)),
    outcome: prev && prev.outcome.code !== cur.outcome.code ? `${prev.outcome.label} → ${cur.outcome.label}` : null,
  }
}
