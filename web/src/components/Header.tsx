import { NavLink } from 'react-router-dom'
import { useApp } from '../state'
import { date } from '../format'

export function Header() {
  const { snapshot, recalculating } = useApp()
  return (
    <header>
      <div className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand">
            <b>Rebalancování portfolií</b>
            <span>Lukas Sysel</span>
          </NavLink>
          <nav className="nav" aria-label="Hlavní navigace">
            <NavLink to="/" end>Přehled</NavLink>
            <NavLink to="/novy-klient">Přidat klienta</NavLink>
            <NavLink to="/metodika">Předpoklady a metodika</NavLink>
          </nav>
          {snapshot && (
            <div className="dataset">
              <span>
                Ocenění k <strong>{date(snapshot.dataset.valuation_date)}</strong>
              </span>
              <span>{snapshot.demo ? 'modelová data ze zadání' : `nahraný soubor ${snapshot.dataset.source}`}</span>
              {recalculating && <span role="status">přepočítává se…</span>}
            </div>
          )}
        </div>
      </div>
      <div className="proposal-note">Návrh – nejde o pokyn k obchodu. Aplikace nemění stav účtů; ceny a kurzy jsou modelové.</div>
    </header>
  )
}
