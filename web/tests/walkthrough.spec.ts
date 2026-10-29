// Evaluator walkthrough, doc 09 §7 tasks 4–14, as automated checks against the running app (baseURL :8123).
import { expect, test } from '@playwright/test'
import path from 'node:path'

const client = (name: string, tab?: string) => `/klient/${encodeURIComponent(name)}${tab ? `?tab=${tab}` : ''}`

test('4–5: A opens on its decision; bands are numeric', async ({ page }) => {
  await page.goto(client('Klient A'))
  const decision = page.locator('.decision')
  await expect(decision).toContainText('Provést nyní')
  const box = await decision.boundingBox()
  expect(box!.y).toBeLessThan(page.viewportSize()!.height)
  await page.getByRole('tab', { name: 'Portfolio' }).click()
  await expect(page.locator('.panel table').first()).toContainText('55,00 %–65,00 %')
})

test('6–8: a tighter tolerance for A changes trades and cost, undo works', async ({ page }) => {
  await page.goto(client('Klient A', 'strategie'))
  await page.fill('#f-band_abs', '1')
  const summary = page.locator('.change-summary')
  await expect(summary).toContainText('pokyny 3 → 5')
  await expect(summary).toContainText('5 537,89 Kč →')
  await expect(summary).not.toContainText('→ 5 537,89 Kč')
  await page.getByRole('button', { name: 'Vrátit změnu' }).click()
  await expect(page.locator('#f-band_abs')).toHaveValue('5')
})

test('9–10: deposit step is conditional and costed; lot tax status visible', async ({ page }) => {
  await page.goto(client('Klient A', 'obchody'))
  const cond = page.locator('.panel tr.cond').filter({ hasText: '10. 11. 2026' })
  await expect(cond).toContainText('podmíněně – po vkladu')
  await expect(cond).toContainText('vklad 10. 11. 2026 600 000 Kč')
  await expect(page.locator('.panel table').first()).toContainText('osvobozeno')
  await page.getByText('hotovost po dnech, převody měn, kroky plánu').click()
  await expect(page.getByRole('heading', { name: 'Vypořádaná hotovost podle data valuty' })).toBeVisible()
})

test('11: decisive ranking step stated with numbers', async ({ page }) => {
  await page.goto(client('Klient A'))
  await expect(page.locator('.decision')).toContainText('Vybrána levnější varianta „Nyní, částečně“ (náklady 5 537,89 Kč); varianta „Nyní, až na cíl“ by stála 6 244,82 Kč.')
})

test('12: restoring the default strategy undoes an edit', async ({ page }) => {
  await page.goto(client('Klient C', 'strategie'))
  await page.fill('#f-band_abs', '0,4')
  await expect(page.locator('.decision .status')).toContainText('Provést nyní')
  await page.getByRole('button', { name: 'Obnovit výchozí strategii' }).click()
  await expect(page.locator('.decision .status')).toContainText('Bez zásahu')
  await expect(page.locator('#f-band_abs')).toHaveValue('5')
})

test('13: E shows the date, the assumption to verify and the saving', async ({ page }) => {
  await page.goto(client('Klient E'))
  const d = page.locator('.decision')
  await expect(d).toContainText('Vyčkat do 23. 11. 2026')
  await expect(d.locator('.order-list')).toContainText('ověřit u brokera: lot z 20. 11. 2023, datum nabytí 22. 11. 2023')
  await expect(d).toContainText('ta by znamenala odhadem 74 987,51 Kč daně')
  await expect(d).toContainText('Čekání sníží celkové náklady o 74 987,51 Kč')
  await page.goto('/')
  await expect(page.locator('.qrow').filter({ hasText: 'Klient E' })).toContainText('Čekání sníží celkové náklady o 74 987,51 Kč')
})

test('14: monthly import shows a change report and activates atomically', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Načíst data (Excel)' }).click()
  await page.setInputFiles('dialog input[type=file]', path.resolve(process.cwd(), '../docs/data_zadani.xlsx'))
  await expect(page.locator('dialog .issues')).toContainText('Klient C: beze změny')
  await page.getByRole('button', { name: 'Použít data' }).click()
  await expect(page.locator('.notice')).toContainText('Minulé návrhy nejsou považovány za provedené')
  await expect(page.locator('.dataset')).toContainText('nahraný soubor')
})

test('B: every order names its rule and numbers; the full record is folded away', async ({ page }) => {
  await page.goto(client('Klient B'))
  const row = page.locator('.decision .order-list tr').filter({ hasText: 'Prodat 350 ks VWCE' })
  await expect(row).toContainText('VWCE +7,09 p. b. / ±5,00 p. b. po rezervě')
  await expect(row).toContainText('výběry 1. 11. 2026 – 15. 1. 2027 (4×) celkem 1 755 000 Kč')
  await expect(row).toContainText('1 211 963 Kč')
  const later = page.locator('.decision .order-list tr').filter({ hasText: 'Prodat 49 ks VWCE' })
  await expect(later).toContainText('výběry 1. 2. 2027 – 1. 3. 2027 (2×) celkem 170 000 Kč')
  await expect(page.locator('.decision')).not.toContainText('Neprovádí se')
  await expect(page.locator('details.record-all')).not.toHaveAttribute('open', '')
})

test('comparison shows the recommendation and its nearest competitor; all on request', async ({ page }) => {
  await page.goto(client('Klient E'))
  const heads = page.locator('table.compare thead th[scope=col]')
  await expect(heads).toHaveCount(3)  // label column + 2 variants
  await page.getByRole('button', { name: /Zobrazit všechny varianty/ }).click()
  await expect(heads).toHaveCount(6)  // label column + 5 variants (E has no deposit to wait for)
})
