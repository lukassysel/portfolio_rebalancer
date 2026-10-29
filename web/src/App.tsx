import { Route, Routes } from 'react-router-dom'
import { Header } from './components/Header'
import { ClientEditor } from './pages/ClientEditor'
import { ClientPage } from './pages/ClientPage'
import { Methodology } from './pages/Methodology'
import { Overview } from './pages/Overview'
import { Report } from './pages/Report'
import { useApp } from './state'

export default function App() {
  const { result, loadError, notice, dismissNotice, error } = useApp()
  return (
    <>
      <Header />
      {notice && (
        <div className="notice" role="status">
          <span>{notice}</span>
          <button className="btn" onClick={dismissNotice}>Zavřít</button>
        </div>
      )}
      {error && <div className="notice error" role="alert">Přepočet se nezdařil: {error} Zobrazené výsledky odpovídají poslední platné strategii.</div>}
      <main id="obsah">
        {loadError && <div className="notice error" role="alert">Data se nepodařilo načíst: {loadError}. Zkontrolujte, že server běží, a obnovte stránku.</div>}
        {!result && !loadError && <p role="status">Načítám data a počítám návrhy…</p>}
        {result && (
          <Routes>
            <Route path="/" element={<Overview />} />
            <Route path="/klient/:name" element={<ClientPage />} />
            <Route path="/klient/:name/zprava" element={<Report />} />
            <Route path="/klient/:name/upravit" element={<ClientEditor key="edit" />} />
            <Route path="/novy-klient" element={<ClientEditor key="new" />} />
            <Route path="/metodika" element={<Methodology />} />
            <Route path="*" element={<p>Stránka neexistuje.</p>} />
          </Routes>
        )}
      </main>
    </>
  )
}
