// What a deviation means, the simple-rule comparison and month-to-month changes (all from engine output).
import { expect, test } from '@playwright/test'
import path from 'node:path'

test('A: band excess in p. b. and CZK, and the equity stress line', async ({ page }) => {
  await page.goto(`/klient/${encodeURIComponent('Klient A')}`)
  const m = page.locator('.decision .meaning')
  await expect(m).toContainText('z toho o 5,82 p. b. nad horní hranicí pásma')
  await expect(m).toContainText('597 706 Kč')
  await expect(m).toContainText('Kdyby akcie klesly o 20')
})

test('overview: B shows breaches visible only after the withdrawal reserve', async ({ page }) => {
  await page.goto('/')
  const b = page.locator('.qrow', { hasText: 'Klient B' })
  await expect(b.locator('.gauge', { hasText: 'VWCE' })).toContainText('po odečtení rezervy')
})

test('overview: comparison with the simple rule, totals from the engine', async ({ page }) => {
  await page.goto('/')
  const t = page.locator('.simple-rule')
  await expect(t.locator('tr', { hasText: 'Klient E' })).toContainText('110 634 Kč')
  await expect(t.locator('tr.total')).toContainText('71 421 Kč')
})

test('next month: new vs. persisting breaches and the cause', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Načíst data (Excel)' }).click()
  await page.setInputFiles('dialog input[type=file]', path.resolve(process.cwd(), '../docs/priklad_dalsi_mesic.xlsx'))
  await expect(page.locator('dialog .issues')).toContainText('Klient C: beze změny pozic, hotovosti, toků i cílů → výsledek Bez zásahu → Zkontrolovat')
  await page.getByRole('button', { name: 'Použít data' }).click()
  await expect(page.locator('.qrow', { hasText: 'Klient A' }).locator('.since')).toContainText('nově mimo pásmo: Hotovost')
  await expect(page.locator('.qrow', { hasText: 'Klient D' }).locator('.since')).toContainText('mimo pásmo i minule')
})
