// New client created in the app → evaluated by the engine → saved to Excel → re-imported unchanged.
import { expect, test } from '@playwright/test'
import fs from 'node:fs'

test('create, evaluate, export and re-import a new client', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Přidat klienta' }).click()
  await page.getByLabel('Jméno klienta').fill('Nová Klientka')
  const target = (label: string, v: string) => page.locator('.targets label').filter({ hasText: label }).locator('input').fill(v)
  await target('VWCE', '40'); await target('AVWS', '10'); await target('EUNA', '40'); await target('IGLN', '5'); await target('Hotovost', '5')
  await page.getByRole('button', { name: 'Přidat pozici' }).click()
  await page.getByLabel('Datum nákupu').fill('2018-05-02')
  await page.getByLabel('Počet kusů').fill('4000')
  await page.getByLabel('Nákupní cena').fill('60')
  await page.getByLabel('Zůstatek').first().fill('150000')
  await page.getByRole('button', { name: 'Přidat tok' }).click()
  await page.getByLabel('Datum toku').fill('2026-12-20')
  await page.getByLabel('Částka').fill('-400000')
  await page.getByRole('button', { name: 'Přidat klienta a vyhodnotit' }).click()

  await expect(page).toHaveURL(/Nov%C3%A1%20Klientka|Nová%20Klientka/)
  await expect(page.locator('.decision .status')).toContainText('Zajistit likviditu do')
  await expect(page.locator('.decision')).toContainText('prodat')
  await expect(page.getByRole('heading', { name: 'Záznam rozhodnutí' })).toBeVisible()

  await page.getByRole('link', { name: 'Přehled', exact: true }).first().click()
  await expect(page.locator('.qrow').filter({ hasText: 'Nová Klientka' })).toBeVisible()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Uložit data (Excel)' }).click()
  const file = await (await download).path()
  expect(fs.statSync(file!).size).toBeGreaterThan(1000)

  await page.reload()  // the data live only in the browser: a reload starts again from the assignment data
  await expect(page.locator('.qrow').filter({ hasText: 'Nová Klientka' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Načíst data (Excel)' }).click()
  await page.setInputFiles('dialog input[type=file]', file!)
  await expect(page.locator('dialog .issues')).toContainText('Nová Klientka: nový klient')
  await page.getByRole('button', { name: 'Použít data' }).click()
  await expect(page.locator('.qrow').filter({ hasText: 'Nová Klientka' })).toContainText('prodat nejpozději15. 12. 2026')
})

test('invalid input is explained and not saved', async ({ page }) => {
  await page.goto('/novy-klient')
  await page.getByLabel('Jméno klienta').fill('Klient A')
  await page.getByRole('button', { name: 'Přidat klienta a vyhodnotit' }).click()
  await expect(page.getByRole('alert')).toContainText('Klient „Klient A“ už existuje.')
  await expect(page.getByRole('alert')).toContainText('Součet cílových vah je 0,00 %')
})

test('a client imported with a data error is evaluated again once fixed in the editor', async ({ page, request }) => {
  const demo = await (await request.get('/api/demo')).json()
  const c = demo.dataset.clients.find((x: { name: string }) => x.name === 'Klient C')
  c.cash = [{ currency: 'CZK', amount: '-5000' }]  // invalid in the workbook: negative cash balance
  const xlsx = await (await request.post('/api/export', { data: { dataset: demo.dataset, policies: demo.policies } })).body()
  const file = test.info().outputPath('chybna-data.xlsx')
  fs.writeFileSync(file, xlsx)

  await page.goto('/')
  await page.getByRole('button', { name: 'Načíst data (Excel)' }).click()
  await page.setInputFiles('dialog input[type=file]', file)
  await page.getByRole('button', { name: 'Použít data' }).click()
  await page.locator('.qrow .who a', { hasText: 'Klient C' }).click()
  await expect(page.locator('.decision .status')).toHaveText('Opravit data')

  await page.getByRole('link', { name: 'Upravit údaje klienta' }).click()
  await page.getByRole('button', { name: 'Přidat měnu' }).click()  // the invalid row was not imported
  await page.getByLabel('Měna').last().selectOption('CZK')
  await page.getByLabel('Zůstatek').last().fill('18000')
  await page.getByRole('button', { name: 'Uložit a přepočítat' }).click()
  await expect(page.locator('.decision .status')).toHaveText('Bez zásahu')
})
