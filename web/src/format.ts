// Display formatting only: every number shown comes from the engine; the UI never computes money.

const nf = (min: number, max: number) =>
  new Intl.NumberFormat('cs-CZ', { minimumFractionDigits: min, maximumFractionDigits: max })
const n0 = nf(0, 0)
const n2 = nf(2, 2)

export const num = (v: string | number | null | undefined, digits = 2) =>
  v === null || v === undefined ? '—' : nf(digits, digits).format(Number(v))

export const czk = (v: string | number | null | undefined, digits = 2) =>
  v === null || v === undefined ? '—' : `${nf(digits, digits).format(Number(v))} Kč`

export const money = (v: string | number, ccy: string) =>
  ccy === 'CZK' ? czk(v) : `${n2.format(Number(v))} ${ccy}`

export const units = (v: number | string) => `${n0.format(Number(v))} ks`
export const int = (v: number | string) => n0.format(Number(v))

export const pct = (v: string | number | null | undefined, digits = 2) =>
  v === null || v === undefined ? '—' : `${nf(digits, digits).format(Number(v))} %`

export const pp = (v: string | number | null | undefined, digits = 2, signed = true) => {
  if (v === null || v === undefined) return '—'
  const x = Number(v)
  const s = nf(digits, digits).format(Math.abs(x))
  const sign = !signed || s.replace(/[0,\s]/g, '') === '' ? '' : x > 0 ? '+' : '−'
  return `${sign}${s} p. b.`
}

export const date = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  return `${d}. ${m}. ${y}`
}

const WD = ['neděle', 'pondělí', 'úterý', 'středa', 'čtvrtek', 'pátek', 'sobota']
export const weekday = (iso: string) => {
  const [y, m, d] = iso.split('-').map(Number)
  return WD[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]
}

/** Percent with only the decimals that matter (targets such as 35 or 12,5). */
export const pctTrim = (v: string | number | null | undefined) =>
  v === null || v === undefined ? '—' : `${nf(0, 2).format(Number(v))}\u00a0%`

/** Czech plural: 1 klient, 2–4 klienti, 5+ klientů. */
export const plural = (n: number, one: string, few: string, many: string) =>
  `${n}\u00a0${n === 1 ? one : n >= 2 && n <= 4 ? few : many}`
