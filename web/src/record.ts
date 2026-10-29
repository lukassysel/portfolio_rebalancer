// Fixed sentence templates for the engine's decision record (rebalancer/engine/explain.py).
// One template per record code, identical for every client; the UI chooses nothing — it only fills in the
// values the engine returned. Unknown codes are shown verbatim so nothing is ever silently hidden.
import type { components } from './api/schema'
import { czk, date, pct, pctTrim, plural, pp, units } from './format'
import { ALT_NAMES, compName } from './texts'

export type Explanation = components['schemas']['Explanation']
export type Summary = components['schemas']['Summary']
export type Tag = components['schemas']['Tag']
type P = Record<string, string>

const alt = (id: string) => ALT_NAMES[id] ?? id
const measure = (m: string) => (m === 'A' ? 'z celého majetku' : m === 'B' ? 'po odečtení rezervy na výběry' : 'po odečtení rezervy')
const yes = (v: string) => v === 'True'
const TIER: P = {
  compliance: 'dodržení pásem', residual: 'zbývající odchylka', cost: 'celkové náklady', orders: 'počet pokynů',
  turnover: 'objem obchodů', timing: 'dřívější termín', id: 'pevné pořadí',
}
const SCENARIO: Record<string, (p: P) => string> = {
  tax_high: (p) => `daň ${pctTrim(p.rate)}`, raw_time_test: () => 'časový test od data nákupu (ne od vypořádání)',
  corporate_0: () => 'daň s.r.o. 0 %', corporate_21: (p) => `daň s.r.o. ${pctTrim(p.rate)} ze zisku`,
}
const scenario = (id: string, p: P = {}) => SCENARIO[id]?.(p) ?? id

const T: Record<string, (p: P) => string> = {
  // decision (the main reason)
  data_error: (p) => `Chyba ve vstupních datech${p.sheet ? ` (${p.sheet}${p.cell ? `!${p.cell}` : ''})` : ''}: ${p.message}`,
  within_bands: (p) => `Všechny složky jsou v pásmech: největší odchylka ${pp(p.max_deviation, 2, false)}, nejmenší vzdálenost od hranice pásma ${pp(p.min_headroom, 2, false)}.`,
  monitor_near_band: (p) => `${compName(p.scope)} je na ${pp(p.deviation)} při pásmu ±${pp(p.band, 2, false)} (${pctTrim(p.ratio)} pásma a více).`,
  monitor_flow_soon: (p) => `Do ${p.days} dnů je naplánován tok ${czk(p.amount)} (${date(p.date)}).`,
  monitor_time_test_soon: (p) => `Lot ${p.scope} splní časový test ${date(p.date)}.`,
  review_residual: (p) => `Žádná přípustná varianta nedrží všechna pásma; zbývající překročení ${pp(p.residual, 2, false)}.`,
  review_uncertain: (p) => `Doporučení se mění při: ${(p.scenarios ?? '').split(',').map((s) => scenario(s, { rate: s === 'tax_high' ? p.tax_high_rate : p.corporate_rate })).join(', ')}.`,
  review_hard_constraints: (p) => `Žádná varianta nesplní tvrdá omezení${p.date ? ` (hotovost ${p.currency} by k ${date(p.date)} byla ${czk(p.amount)})` : ''}.`,
  review_withdrawals_uncovered: (p) => `Výběr ${date(p.date)} nelze pokrýt ani prodejem všech pozic: chybí ${czk(p.shortfall)}, k dispozici ${czk(p.max_available)}.`,
  wait_saves: (p) => `Čekání sníží celkové náklady o ${czk(p.saving)} oproti variantě ${alt(p.compared_with)}${p.avoided_tax ? ` (ta by znamenala odhadem ${czk(p.avoided_tax)} daně)` : ''}; požadované minimum ${czk(p.min_saving)}.`,
  wait_deposit_saves: (p) => `Čekání na vklad sníží celkové náklady o ${czk(p.saving)} oproti variantě ${alt(p.compared_with)}; požadované minimum ${czk(p.min_saving)}.`,
  liquidity_shortfall: (p) => `Bez prodeje by na výběr ${date(p.withdrawal_date)} chybělo ${czk(p.shortfall)}; prodat nejpozději ${date(p.latest_sale)}.`,
  band_breach: (p) => `${compName(p.scope)} ${pp(p.deviation)} od cíle (${measure(p.measure)}), povoleno ±${pp(p.band, 2, false)}.`,
  idle_cash: (p) => `Nevyužitá hotovost ${pct(p.deviation)} majetku, povoleno nejvýše ${pct(p.band)}.`,
  future_breach: (p) => `${compName(p.scope)} vybočí z pásma k ${date(p.date)}.`,
  // bands
  band_check: (p) => `${compName(p.scope)} ${measure(p.measure)}: ${pct(p.value)} (cíl ${pct(p.target)}, pásmo ${pct(p.low)}–${pct(p.high)})`,
  // liquidity
  withdrawal: (p) => `Výběr ${czk(p.amount)} k ${date(p.date)} (z účtu ${date(p.value_date)}): bez obchodů ${'{covered}'}; prodej pro něj nejpozději ${date(p.latest_sale)}; ${yes(p.within_reserve) ? 'je v povinné rezervě' : `do rezervy vstoupí ${date(p.reserve_from)}`}.`,
  deposit: (p) => `Vklad ${czk(p.amount)} k ${date(p.date)}, použitelný od ${date(p.value_date)}.`,
  // alternatives
  generated: (p) =>
    p.because === 'baseline' ? `${alt(p.id)}: srovnávací základ.`
      : p.because === 'always' ? `${alt(p.id)}: počítá se vždy.`
        : p.because === 'deposit' ? `${alt(p.id)}: vklad ${date(p.date)} je za ${p.days} dnů.`
          : `${alt(p.id)}: lot ${p.ticker} z ${date(p.acquired)} bude osvobozen od daně ${date(p.date)} (za ${p.days} dnů).`,
  skipped: (p) => `Čekání na ${p.kind === 'wait_deposit' ? `vklad ${date(p.date)}` : `osvobození lotu ${p.ticker} z ${date(p.acquired)} (${date(p.date)})`} se nezvažuje: ${p.days} dnů je víc než limit ${p.max_days} dnů.`,
  result: (p) => `${alt(p.id)}: ${yes(p.feasible) ? 'proveditelná' : `neproveditelná (hotovost ${p.violation_currency} k ${date(p.violation_date)})`}, ${Number(p.residual) > 0 ? `pásma nedrží (překročení ${pp(p.residual, 2, false)})` : 'pásma drží'}, náklady ${czk(p.cost)}, ${p.orders} pokynů.`,
  // ranking
  rank: (p) => `${p.position}. ${alt(p.id)} – náklady ${czk(p.cost)}, ${p.orders} pokynů, objem ${czk(p.turnover, 0)}${Number(p.residual) > 0 ? `, překročení pásem ${pp(p.residual, 2, false)}` : ''}.`,
  excluded: (p) => `${alt(p.id)} vyřazena: ${p.because === 'infeasible' ? 'neproveditelná' : p.because === 'wait_test' ? 'nesplnila test čekání' : 'nepřípustná'}.`,
  decisive: (p) => p.tier === 'cost'
    ? `Vybrána levnější varianta „${alt(p.winner)}“ (náklady ${czk(p.winner_value)}); varianta „${alt(p.runner_up)}“ by stála ${czk(p.runner_up_value)}.`
    : `Rozhodlo kritérium „${TIER[p.tier] ?? p.tier}“: „${alt(p.winner)}“${p.winner_value ? ` ${p.winner_value}` : ''} oproti „${alt(p.runner_up)}“${p.runner_up_value ? ` ${p.runner_up_value}` : ''}.`,
  // waiting
  wait_test: (p) => `Test čekání (${alt(p.id)}): ${p.days} z max. ${p.max_days} dnů; odchylka během čekání ${pp(p.max_deviation, 2, false)} z max. ${pp(p.deviation_cap, 0, false)}; úspora ${p.saving ? czk(p.saving) : '—'} (min. ${czk(p.min_saving)}${p.saving_high_tax ? `, při dani ${pctTrim(p.high_rate)} ${czk(p.saving_high_tax)}` : ''}).`,
  // sensitivity
  scenario: (p) => `Citlivost – ${scenario(p.scenario, p)}: ${p.recommended ? alt(p.recommended) : 'žádná přípustná varianta'}.`,
  // assumptions
  time_test_date: (p) => `Předpoklad k ověření: lot ${p.ticker} nakoupen ${date(p.purchase)}, datum nabytí ${date(p.acquisition)} (vypořádání nákupu, GFŘ D-59), výročí nákupu ${date(p.anniversary)}, osvobozen od ${date(p.first_exempt)}; prodej ${date(p.sale)}, vypořádání ${date(p.settlement)}. Ověřte u brokera skutečné datum připsání a před obchodem přepočítejte.`,
  corporate_tax_unknown: (p) => `Daň s.r.o. z dat nelze určit (chybí účetní hodnoty); podmíněný odhad ${pct(p.rate, 0)} ze zisku je uveden zvlášť.`,
  tax_rate: (p) => `Daň odhadnuta sazbou ${pct(p.rate, 0)}, citlivost ${pct(p.high, 0)}.`,
}

export function explain(e: Explanation): string {
  const f = T[e.code]
  if (!f) return `${e.code} ${JSON.stringify(e.params)}`
  const text = f(e.params as P).replace(/b\.\./g, 'b.')
  return e.code === 'withdrawal' ? text.replace('{covered}', e.passed ? 'kryt' : 'nekryt') : text
}

// Reason tags: one short label per rule code, the numbers come from the engine.
const TAG: Record<string, (p: P) => string> = {
  band: (p) => `${compName(p.scope)} ${pp(p.deviation)} / ±${pp(p.band, 2, false)}${p.measure === 'B' ? ' po rezervě' : ''}`,
  equity_band: (p) => `Akcie celkem ${pp(p.deviation)} / ±${pp(p.band, 2, false)}${p.measure === 'B' ? ' po rezervě' : ''}`,
  idle_cash: (p) => `nevyužitá hotovost ${pct(p.deviation)} > ${pctTrim(p.band)}`,
  cash_band: (p) => `hotovost ${pp(p.deviation)} / ±${pp(p.band, 2, false)}`,
  to_target: (p) => `${compName(p.scope)} ${pp(p.deviation)} od cíle`,
  withdrawal: (p) => Number(p.count) > 1
    ? `výběry ${date(p.date)} – ${date(p.last)} (${p.count}×) celkem ${czk(p.amount, 0)}`
    : `výběr ${date(p.date)} ${czk(p.amount, 0)}`,
  cash_target: (p) => `cílová hotovost ${pctTrim(p.target)}`,
  deposit: (p) => `vklad ${date(p.date)} ${czk(p.amount, 0)}`,
  after_time_test: (p) => `po časovém testu ${date(p.date)}`,
  fx: (p) => `převod ${p.source}→${p.target} ${czk(p.cost, 0)}`,
  taxable_gain: (p) => `daň ≈ ${czk(p.tax, 0)} (${pctTrim(p.rate)} ze zisku ${czk(p.gain, 0)})`,
  verify_acquisition: (p) => `ověřit u brokera: lot z ${date(p.acquired)}, datum nabytí ${date(p.acquisition)} (předpoklad)`,
}

export function tagText(t: Tag): string {
  const f = TAG[t.code]
  return f ? f((t.params ?? {}) as P).replace(/b\.\./g, 'b.') : `${t.code} ${JSON.stringify(t.params)}`
}

export const TAG_CLASS: Record<string, string> = { reason: 'reason', info: '', warning: 'warn' }

export const SECTIONS: { id: string; title: string }[] = [
  { id: 'decision', title: 'Rozhodnutí' },
  { id: 'bands', title: 'Kontrola tolerančních pásem (dnes)' },
  { id: 'liquidity', title: 'Hotovost: vklady a výběry' },
  { id: 'alternatives', title: 'Posuzované varianty' },
  { id: 'ranking', title: 'Pořadí variant' },
  { id: 'waiting', title: 'Test čekání' },
  { id: 'sensitivity', title: 'Citlivost na nejisté předpoklady' },
  { id: 'assumptions', title: 'Předpoklady' },
]

const brief = (os: { side: string; ticker: string; units: number }[], side: string) =>
  os.filter((o) => o.side === side).map((o) => `${units(o.units)} ${o.ticker}`)

/** "prodat …, koupit …" from an engine order list (formatting only). */
export function ordersText(os: { side: string; ticker: string; units: number }[]): string {
  const s = brief(os, 'SELL')
  const b = brief(os, 'BUY')
  const j = (xs: string[]) => (xs.length <= 1 ? xs.join('') : `${xs.slice(0, -1).join(', ')} a ${xs[xs.length - 1]}`)
  return [s.length ? `prodat ${j(s)}` : '', b.length ? `koupit ${j(b)}` : ''].filter(Boolean).join(', ')
}

export const KEY_DATE: P = {
  trade: 'obchod', latest_sale: 'prodat nejpozději', wait_until: 'vyčkat do', review: 'další kontrola',
}
const STEP_KIND: P = { planned: 'plánováno', conditional: 'podmíněně' }
const STEP_REASON: P = { wait_tax: 'po splnění časového testu', wait_deposit: 'po vkladu', deposit: 'po vkladu', reserve: 'doplnění rezervy', now: 'dokončení dnešního kroku' }

/** Headline built only from the engine summary. */
export function headline(s: Summary | null | undefined, outcomeLabel: string): string {
  if (!s) return outcomeLabel
  const today = ordersText(s.today)
  const first = s.later[0]
  if (!today && !first) return s.key_date_kind === 'review' ? 'Bez obchodů' : outcomeLabel
  const parts = []
  if (today) parts.push(`Dnes: ${today}`)
  if (first) parts.push(`${date(first.date)} (${STEP_KIND[first.kind]}, ${STEP_REASON[first.reason] ?? first.reason}): ${ordersText(first.orders)}`)
  if (s.later.length > 1) parts.push(`+ ${plural(s.later.length - 1, 'další krok', 'další kroky', 'dalších kroků')}`)
  return parts.join('; ')
}

/** Short form for the overview: today's orders, otherwise the first later step. */
export function shortStep(s: Summary | null | undefined, outcomeLabel: string): string {
  if (!s) return outcomeLabel
  const today = ordersText(s.today)
  const first = s.later[0]
  if (today) return `Dnes ${today}${s.later.length ? ` (+ ${plural(s.later.length, 'pozdější krok', 'pozdější kroky', 'pozdějších kroků')})` : ''}`
  if (first) return `${date(first.date)}: ${ordersText(first.orders)}`
  return s.key_date_kind === 'review' ? 'Bez obchodů' : outcomeLabel
}
