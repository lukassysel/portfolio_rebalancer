import type { Dataset, EvaluationResult, Issue, Meta, Policy, Snapshot } from './types'

export class ApiError extends Error {
  issues: Issue[]
  constructor(message: string, issues: Issue[] = []) {
    super(message)
    this.issues = issues
  }
}

async function json<T>(r: Response): Promise<T> {
  if (r.ok) return r.json() as Promise<T>
  let body: { detail?: unknown; issues?: Issue[] } = {}
  try {
    body = await r.json()
  } catch {
    /* non-JSON error */
  }
  const detail = typeof body.detail === 'string' ? body.detail : `Server vrátil chybu ${r.status}.`
  throw new ApiError(detail, body.issues ?? [])
}

export const getDemo = () => fetch('/api/demo').then((r) => json<Snapshot>(r))
export const getMeta = () => fetch('/api/meta').then((r) => json<Meta>(r))

export function postEvaluate(
  modelVersion: string,
  dataset: Dataset,
  policies: Record<string, Policy>,
  issues: Issue[],
  signal?: AbortSignal,
) {
  return fetch('/api/evaluate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model_version: modelVersion, dataset, policies, issues }),
    signal,
  }).then((r) => json<EvaluationResult>(r))
}

export function postImport(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return fetch('/api/import', { method: 'POST', body: fd }).then((r) => json<Snapshot>(r))
}

/** Download the current client book (data + strategies) as an .xlsx in the import format. */
export async function downloadWorkbook(dataset: Dataset, policies: Record<string, Policy>) {
  const r = await fetch('/api/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset, policies }),
  })
  if (!r.ok) throw new ApiError(`Export se nezdařil (${r.status}).`)
  const blob = await r.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `klienti-${dataset.valuation_date}.xlsx`
  a.click()
  URL.revokeObjectURL(a.href)
}
