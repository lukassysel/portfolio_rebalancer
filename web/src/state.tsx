// App state lives in the browser only (stateless server, no localStorage — doc 07 §8 item 5).
// Every policy edit re-evaluates the full payload; only the latest revision is ever rendered.
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { ApiError, getDemo, postEvaluate, postImport } from './api/client'
import type { Dataset, EvaluationResult, Policy, Snapshot } from './api/types'

type State = {
  snapshot: Snapshot | null
  policies: Record<string, Policy>
  result: EvaluationResult | null
  recalculating: boolean
  error: string | null
  notice: string | null
  loadError: string | null
  stale: Record<string, boolean>
  unsaved: boolean
  previous: EvaluationResult | null // result before the last import: new vs. persisting breaches
}

type Ctx = State & {
  setPolicy: (client: string, p: Policy) => void
  resetPolicy: (client: string) => void
  updateBook: (dataset: Dataset, policies: Record<string, Policy>, defaults: Record<string, Policy>, notice?: string) => void
  importFile: (f: File) => Promise<Snapshot>
  activate: (s: Snapshot, keep?: Record<string, Policy>) => void
  dismissNotice: () => void
  markStale: (client: string, stale: boolean) => void
  markSaved: () => void
}

const AppCtx = createContext<Ctx | null>(null)

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({
    snapshot: null,
    policies: {},
    result: null,
    recalculating: false,
    error: null,
    notice: null,
    loadError: null,
    stale: {},
    unsaved: false,
    previous: null,
  })
  const revision = useRef(0)
  const abort = useRef<AbortController | null>(null)

  const activate = useCallback((s: Snapshot, notice: string | null = null, previous: EvaluationResult | null = null) => {
    revision.current += 1
    abort.current?.abort()
    setState({ snapshot: s, policies: s.policies, result: s.result, recalculating: false, error: null, notice, loadError: null, stale: {}, unsaved: false, previous })
  }, [])

  useEffect(() => {
    getDemo()
      .then((s) => activate(s))
      .catch((e: Error) => setState((st) => ({ ...st, loadError: e.message })))
  }, [activate])

  // Data live only in this browser tab: warn before a reload or close would discard changes (owner: Excel is the store).
  useEffect(() => {
    if (!state.unsaved) return
    const warn = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [state.unsaved])

  const latest = useRef(state)
  latest.current = state

  // Only the newest revision may update the screen; older responses are discarded (doc 07 §8 item 5).
  const recalc = useCallback((policies: Record<string, Policy>, snapshot?: Snapshot) => {
    const snap = snapshot ?? latest.current.snapshot
    if (!snap) return
    const rev = ++revision.current
    abort.current?.abort()
    const ctrl = new AbortController()
    abort.current = ctrl
    setState((st) => ({ ...st, policies, recalculating: true, unsaved: st.unsaved || policies !== st.snapshot?.policies }))
    postEvaluate(snap.model_version, snap.dataset, policies, snap.issues, ctrl.signal)
      .then((result) => {
        if (rev === revision.current) setState((st) => ({ ...st, result, recalculating: false, error: null }))
      })
      .catch((e: Error) => {
        if (e.name !== 'AbortError' && rev === revision.current)
          setState((st) => ({ ...st, recalculating: false, error: e.message }))
      })
  }, [])

  const setPolicy = useCallback(
    (client: string, p: Policy) => recalc({ ...latest.current.policies, [client]: p }),
    [recalc],
  )

  const resetPolicy = useCallback(
    (client: string) => {
      const snap = latest.current.snapshot
      if (snap) recalc({ ...latest.current.policies, [client]: snap.policies[client] })
    },
    [recalc],
  )

  // Client added, edited or removed in the browser: new dataset + strategies, evaluated by the engine at once.
  const updateBook = useCallback(
    (dataset: Dataset, policies: Record<string, Policy>, defaults: Record<string, Policy>, notice?: string) => {
      const snap = latest.current.snapshot
      if (!snap) return
      // import issues of a client the editor changed no longer apply: the engine re-validates the new data itself
      const before = new Map(snap.dataset.clients.map((c) => [c.name, JSON.stringify(c)]))
      const changed = new Set(dataset.clients.filter((c) => before.get(c.name) !== JSON.stringify(c)).map((c) => c.name))
      const names = new Set(dataset.clients.map((c) => c.name))
      const issues = snap.issues.filter((i) => !i.client || (names.has(i.client) && !changed.has(i.client)))
      const next = { ...snap, dataset, policies: defaults, issues, demo: false }
      setState((st) => ({ ...st, snapshot: next, notice: notice ?? st.notice, unsaved: true }))
      recalc(policies, next)
    },
    [recalc],
  )

  const importFile = useCallback(async (f: File) => {
    try {
      return await postImport(f)
    } catch (e) {
      if (e instanceof ApiError) throw e
      throw new ApiError((e as Error).message)
    }
  }, [])

  const value: Ctx = {
    ...state,
    setPolicy,
    resetPolicy,
    updateBook,
    importFile,
    activate: (s: Snapshot, keep?: Record<string, Policy>) => {
      activate(
        s,
        `Data nahrazena k ${s.dataset.valuation_date.split('-').reverse().map(Number).join('. ')}. ` +
          'Minulé návrhy nejsou považovány za provedené – nová data musí obsahovat skutečný stav účtů.',
        state.result,
      )
      const names = Object.keys(keep ?? {}).filter((n) => s.policies[n])
      if (names.length) {
        // edited strategies kept by client name; target weights always come from the new file (doc 07 §8 item 4)
        const policies = { ...s.policies }
        for (const n of names) policies[n] = { ...keep![n], targets: s.policies[n].targets }
        recalc(policies, s)
      }
    },
    dismissNotice: () => setState((st) => ({ ...st, notice: null })),
    markSaved: () => setState((st) => ({ ...st, unsaved: false })),
    markStale: (client: string, flag: boolean) =>
      setState((st) => (!!st.stale[client] === flag ? st : { ...st, stale: { ...st.stale, [client]: flag } })),
  }
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>
}

export function useApp() {
  const c = useContext(AppCtx)
  if (!c) throw new Error('useApp outside provider')
  return c
}
