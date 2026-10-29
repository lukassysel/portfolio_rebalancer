import { test, expect, type Page, type TestInfo } from '@playwright/test'

async function capture(page: Page, info: TestInfo, name: string) {
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: info.outputPath(`${name}-${info.project.name}.png`), fullPage: true })
}

test('overview groups form the five-client work queue', async ({ page }, info) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Přehled klientů' })).toBeVisible()
  await expect(page.locator('.queue-group h2')).toHaveText(['Zajistit likviditu', 'Provést nyní', 'Vyčkat', 'Bez zásahu'])
  await expect(page.locator('.qrow .who a')).toHaveText(['Klient B', 'Klient A', 'Klient D', 'Klient E', 'Klient C'])
  await expect(page.getByLabel('Souhrn')).toContainText('celkem 5 klientů')
  await capture(page, info, 'overview')
})

test('B explains liquidity outcome using the API deadline', async ({ page, request }, info) => {
  const response = await request.get('/api/demo')
  expect(response.ok()).toBeTruthy()
  const snapshot = await response.json()
  const client = snapshot.result.clients.find((c: { name: string }) => c.name === 'Klient B')
  expect(client.outcome.code).toBe('ensure_liquidity')
  await page.goto('/klient/Klient%20B')
  await expect(page.locator('.decision .status')).toHaveText(client.outcome.label)
  await expect(page.locator('.decision')).toContainText('prodat nejpozději')
  await capture(page, info, 'client-b')
})

test('E waits until 23 November and each tab renders', async ({ page }, info) => {
  await page.goto('/klient/Klient%20E')
  await expect(page.locator('.decision .status')).toHaveText('Vyčkat do 23. 11. 2026')
  await expect(page.locator('.decision .order-list')).toContainText('ověřit u brokera')
  const tabs = ['Rozhodnutí a varianty', 'Obchody a hotovost', 'Portfolio', 'Strategie']
  for (const [i, name] of tabs.entries()) {
    await page.getByRole('tab', { name, exact: true }).click()
    await expect(page.getByRole('tab', { name, exact: true })).toHaveAttribute('aria-selected', 'true')
    await expect(page.getByRole('tabpanel')).toBeVisible()
    await capture(page, info, `client-e-tab-${i + 1}`)
  }
})

test('C absolute tolerance 5 to 0,4 flips the decision', async ({ page }, info) => {
  await page.goto('/klient/Klient%20C')
  await expect(page.locator('.decision .status')).toHaveText('Bez zásahu')
  await page.getByRole('tab', { name: 'Strategie', exact: true }).click()
  const tolerance = page.getByLabel('Absolutní tolerance', { exact: false })
  await expect(tolerance).toHaveValue('5')
  await tolerance.fill('0,4')
  await expect(page.locator('.decision .status')).toHaveText('Provést nyní')
  await expect(page.locator('.change-summary')).toContainText('Bez zásahu → Provést nyní')
  await capture(page, info, 'client-c-strategy')
})

test('import rejects a non-xlsx file without activating it', async ({ page }, info) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Načíst data (Excel)', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: 'Načíst data (Excel)' })
  await dialog.getByLabel('Vybrat soubor').evaluate((element) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File(['not an Excel workbook'], 'invalid.txt', { type: 'text/plain' }))
    ;(element as HTMLInputElement).files = transfer.files
    element.dispatchEvent(new Event('change', { bubbles: true }))
  })
  await expect(dialog.getByRole('alert')).toContainText('Soubor není platný sešit Excel (.xlsx).')
  await expect(dialog.getByRole('alert')).toContainText('Současná data zůstávají beze změny.')
  await expect(dialog.getByRole('button', { name: 'Použít data' })).toBeDisabled()
  await capture(page, info, 'import-rejected')
})

test('methodology renders the assumptions', async ({ page }, info) => {
  await page.goto('/metodika')
  await expect(page.getByRole('heading', { name: 'Předpoklady a metodika', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Jak vzniká doporučení' })).toBeVisible()
  await expect(page.locator('.prose')).toContainText('předpoklad k ověření u brokera')
  await capture(page, info, 'methodology')
})
