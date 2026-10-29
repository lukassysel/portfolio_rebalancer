// Printable per-client report (deliverable D3 in the app): generated from the same engine result as every screen.
import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { czk, date, int, money, pct, pctTrim, pp } from '../format'
import { useApp } from '../state'
import { alt, compName, feeText, nextStep, reason } from '../texts'
import { Tags } from './ClientPage'
import { explain } from '../record'
import { Meaning } from '../components/Meaning'

export function Report() {
  const { name = '' } = useParams()
  const { result, snapshot, recalculating, stale, error } = useApp()
  const c = result?.clients.find((x) => x.name === name)
  useEffect(() => {
    document.title = `Zpráva – ${name}`
  }, [name])
  if (!result || !snapshot || !c) return <p>Klient „{name}“ v datech není. <Link to="/">Zpět na přehled</Link></p>
  const asOf = result.valuation_date
  const rec = alt(c, c.recommended)
  const step = nextStep(c)
  const v = c.valuation
  return (
    <article className="report">
      <div className="no-print" style={{ display: 'flex', gap: 10, marginBottom: 18 }}>
        <Link className="btn" to={`/klient/${encodeURIComponent(c.name)}`}>Zpět na klienta</Link>
        {/* print only a result that matches the current inputs */}
        {recalculating || stale[c.name] || error
          ? <span className="stale" role="status">Zpráva čeká na dokončený přepočet – tisk je dočasně nedostupný.</span>
          : <button className="btn primary" onClick={() => window.print()}>Vytisknout nebo uložit jako PDF</button>}
      </div>
      <h1>{c.name}: {c.outcome.label}</h1>
      <p className="muted">
        Ocenění k {date(asOf)}, {snapshot.demo ? 'modelová data ze zadání' : snapshot.dataset.source}. Návrh – nejde o pokyn
        k obchodu. Verze modelu {result.model_version}.
      </p>
      <h2>Doporučení</h2>
      <p><b>{step.action}</b>{step.when && <> ({step.whenType} {step.when})</>}.</p>
      <p>{reason(c)}.</p>
      {(c.explanations ?? []).filter((e) => e.code === 'decisive').map((e, k) => <p key={k}>{explain(e)}</p>)}
      {v && (
        <>
          <h2>Současný stav</h2>
          <table>
            <thead><tr><th>Složka</th><th className="n">Hodnota</th><th className="n">Váha</th><th className="n">Cíl</th><th className="n">Odchylka</th><th>Pásmo</th></tr></thead>
            <tbody>
              {[...v.components, v.equity].map((x) => (
                <tr key={x.key}>
                  <td>{compName(x.key)}{x.breach ? ' – mimo pásmo' : ''}</td><td className="n">{czk(x.value)}</td>
                  <td className="n">{pct(x.weight)}</td><td className="n">{pctTrim(x.target)}</td><td className="n">{pp(x.deviation)}</td>
                  <td>{pct(x.band_low)}–{pct(x.band_high)}</td>
                </tr>
              ))}
              <tr><td><b>Majetek celkem</b></td><td className="n"><b>{czk(v.nav)}</b></td><td colSpan={4} /></tr>
            </tbody>
          </table>
          <Meaning c={c} asOf={asOf} />
        </>
      )}
      {rec && rec.orders.length > 0 && (
        <>
          <h2>Navržené obchody</h2>
          <table>
            <thead><tr><th>Obchod</th><th>Pokyn</th><th className="n">Kusy</th><th className="n">Hrubě</th><th className="n">Poplatek</th><th>Důvod</th></tr></thead>
            <tbody>
              {rec.orders.map((o, k) => (
                <tr key={k}>
                  <td>{date(o.trade_date)}{o.conditional ? ' (podmíněně)' : o.trade_date > asOf ? ' (plánováno)' : ''}</td>
                  <td>{o.side === 'BUY' ? 'Nákup' : 'Prodej'} {o.ticker}</td><td className="n">{int(o.units)}</td>
                  <td className="n">{money(o.gross, o.currency)}</td><td className="n">{czk(o.commission_czk)}</td>
                  <td><Tags tags={o.tags} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p>
            Náklady celkem <b>{czk(rec.total_cost)}</b>: poplatky {czk(rec.commissions)}, převod měn {czk(rec.fx_cost)},
            odhad daně {rec.tax === null ? 'nelze určit (s.r.o.)' : czk(rec.tax)}.
          </p>
        </>
      )}
      {(() => {
        const lot = v?.lots.find((l) => l.tax_status === 'pending' && c.recommended?.startsWith('WAIT_TAX') && l.first_exempt === c.outcome.date)
        if (!lot) return null
        const sale = rec?.orders.find((o) => o.side === 'SELL' && o.trade_date === lot.first_exempt)
        return (
          <div className="assume">
            <b>Předpoklad k ověření před obchodem {date(lot.first_exempt)}.</b> Lot {lot.ticker}: nákup {date(lot.acquired)},
            předpokládané datum nabytí {date(lot.assumed_acquisition)} (vypořádání nákupu, GFŘ D-59), první den osvobození podle
            modelu {date(lot.first_exempt)}{sale && <>, vypořádání prodeje {date(sale.settlement_date)}</>}. Ověřte u brokera skutečné
            datum připsání; kdyby bylo pozdější, prodej by byl zdanitelný. Před provedením znovu přepočítat.
          </div>
        )
      })()}
      <h2>Předpoklady</h2>
      <p className="muted">
        {feeText(result.assumptions)}; vypořádání T+2, převedená měna k dispozici další pracovní den.
        Daňový odhad je modelový (časový test od vypořádání nákupu, nákupní cena dnešním kurzem); před obchodem přepočítat.
      </p>
    </article>
  )
}
