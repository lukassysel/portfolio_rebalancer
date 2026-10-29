// Czech wording for engine codes. The engine returns structured records; wording lives here only.
import type { Alternative, ClientResult } from './api/types'
import { date, int, pctTrim } from './format'
import { KEY_DATE, explain, headline } from './record'

export const OUTCOME_GROUP: Record<string, string> = {
  fix_data: 'Opravit data',
  ensure_liquidity: 'Zajistit likviditu',
  review: 'Posoudit',
  execute_now: 'Provést nyní',
  wait: 'Vyčkat',
  check: 'Zkontrolovat',
  no_action: 'Bez zásahu',
}
export const QUEUE_ORDER = ['fix_data', 'ensure_liquidity', 'review', 'execute_now', 'wait', 'check', 'no_action']

export const ALT_NAMES: Record<string, string> = {
  BASE: 'Bez obchodů',
  NOW_P: 'Nyní, částečně',
  NOW_T: 'Nyní, až na cíl',
  WAIT_DEP_P: 'Po vkladu, částečně',
  WAIT_DEP_T: 'Po vkladu, až na cíl',
  WAIT_TAX_P: 'Po časovém testu, částečně',
  WAIT_TAX_T: 'Po časovém testu, až na cíl',
}

export const COMPONENT_NAMES: Record<string, string> = { CASH: 'Hotovost', EQ: 'Akcie celkem' }
export const compName = (k: string) => COMPONENT_NAMES[k] ?? k

export const STEP_REASON: Record<string, string> = {
  now: 'krok dnes',
  deposit: 'po vkladu',
  wait_tax: 'po časovém testu',
  wait_deposit: 'po vkladu',
  reserve: 'doplnění rezervy',
}

export const TAX_STATUS: Record<string, string> = {
  exempt: 'osvobozeno (časový test splněn)',
  pending: 'zatím zdanitelné',
  taxable: 'zdanitelné',
  corporate: 's.r.o. – bez časového testu',
}

export function alt(c: ClientResult, id: string | null | undefined): Alternative | undefined {
  return c.alternatives.find((a) => a.id === id)
}

/** Next step and reason for the overview and the decision block — read from the engine summary only. */
export function nextStep(c: ClientResult): { action: string; when: string; whenType: string } {
  const s = c.summary
  return {
    action: headline(s, c.outcome.label),
    when: s?.key_date ? date(s.key_date) : '',
    whenType: s?.key_date_kind ? KEY_DATE[s.key_date_kind] : '',
  }
}

/** Model assumptions as the engine reports them (result.assumptions / meta.assumptions). */
type A = Record<string, unknown> | object | undefined
const get = (a: A, k: string) => String((a as Record<string, unknown> | undefined)?.[k] ?? 0)
const r100 = (a: A, k: string) => pctTrim(Number(get(a, k)) * 100)
export const feeText = (a: A) =>
  `Poplatek ${r100(a, 'commission_rate')} z objemu, min. ${int(get(a, 'commission_min'))} EUR/USD za pokyn; převod měn ${r100(a, 'fx_cost')} jen z převedené částky`
export const taxText = (a: A) =>
  `časový test ${get(a, 'time_test_years')} roky, osvobození příjmů do ${int(get(a, 'receipts_exemption'))} Kč ročně, sazba ${r100(a, 'tax_rate')} (citlivost ${r100(a, 'tax_rate_high')})`
export const taxCols = (a: A) => `Odhad daně ${r100(a, 'tax_rate')} (${r100(a, 'tax_rate_high')})`

export function reason(c: ClientResult): string {
  return c.summary ? explain(c.summary.reason) : ''
}
