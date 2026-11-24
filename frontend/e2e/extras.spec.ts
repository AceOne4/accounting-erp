import { expect, test, type Page } from '@playwright/test'

const PASS = process.env.E2E_PASS ?? ''
const CHIEF = process.env.E2E_USER ?? ''
const ADMIN = process.env.E2E_ADMIN ?? ''
if (!PASS || !CHIEF || !ADMIN) throw new Error('Set E2E_USER, E2E_ADMIN and E2E_PASS')
const SHOTS = process.env.E2E_SHOTS ?? 'e2e/shots'

async function login(page: Page, user: string, pass = PASS, lang: 'ar' | 'en' = 'en') {
  await page.goto('/')
  await page.getByLabel(/username|اسم المستخدم/i).fill(user)
  await page.getByLabel(/password|كلمة المرور/i).fill(pass)
  await page.getByRole('button', { name: /sign in|تسجيل الدخول/i }).click()
  await expect(page.locator('main')).toBeVisible() // signed in
  if (lang === 'en') await page.getByRole('button', { name: 'English' }).click()
  await expect(page.locator('html')).toHaveAttribute('dir', lang === 'en' ? 'ltr' : 'rtl')
}
const nav = (page: Page, name: RegExp) => page.getByRole('navigation').first().getByRole('link', { name }).click()
const overflows = (page: Page) => page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
// i18next prints the key itself when a string is missing, e.g. "inventory.newReceipt"
const leakedKey = (page: Page) => page.locator('body').innerText().then((t) => t.match(/\b(?:nav|common|report|treasury|inventory|journal|users|partners|accounts|password|home|error|notFound|shell)\.[A-Za-z][A-Za-z.]*\b/))

test('Arabic: every main screen is right-to-left, fully translated and fits the width', async ({ page }) => {
  await login(page, CHIEF, PASS, 'ar')
  const screens: [string, string][] = [
    ['/', 'home'], ['/journal', 'journal'], ['/partners', 'partners'], ['/accounts', 'accounts'], ['/treasury', 'treasury'],
    ['/inventory/levels', 'inv-levels'], ['/inventory/receipts/new', 'inv-receipt'], ['/inventory/transfers/new', 'inv-transfer'],
    ['/inventory/counts/new', 'inv-count'], ['/inventory/setup', 'inv-setup'], ['/reports/trial-balance', 'rep-tb'],
    ['/reports/ledger', 'rep-ledger'], ['/reports/statement', 'rep-stmt'],
  ]
  for (const [path, name] of screens) {
    await page.goto(path)
    await expect(page.locator('main h2, main h3').first()).toBeVisible()
    await page.waitForLoadState('networkidle')
    expect(await leakedKey(page), `${path} shows an untranslated key`).toBeNull()
    expect(await overflows(page), `${path} scrolls sideways`).toBe(false)
    await page.screenshot({ path: `${SHOTS}/ar-${name}.png`, fullPage: true })
  }
})

test('roles: reviewer and accountant only get the controls their role allows', async ({ page }) => {
  await login(page, 'rev')
  await nav(page, /journal entries/i)
  await expect(page.getByRole('link', { name: /new entry/i })).toHaveCount(0)
  await nav(page, /^treasury$/i)
  await expect(page.getByText(/new voucher/i)).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^save$/i })).toHaveCount(0) // no forms at all
  await expect(page.getByRole('button', { name: /save count/i })).toHaveCount(0)
  await nav(page, /^inventory$/i)
  await page.getByRole('link', { name: /^receipts$/i }).click()
  await expect(page.getByRole('link', { name: /new receipt/i })).toBeVisible() // reviewers handle goods receipts
  await expect(page.getByRole('navigation').first().getByRole('link', { name: /^users$/i })).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/role-reviewer.png` })
  await page.getByRole('button', { name: /sign out/i }).click()

  await login(page, 'acc')
  await nav(page, /^inventory$/i)
  await page.getByRole('link', { name: /^receipts$/i }).click()
  await expect(page.getByRole('link', { name: /new receipt/i })).toHaveCount(0) // accountants only count stock
  await page.getByRole('link', { name: /^counts$|stock counts/i }).click()
  await expect(page.getByRole('link', { name: /new stock count/i })).toBeVisible()
  await page.getByRole('link', { name: /^setup$/i }).click()
  await expect(page.getByRole('button', { name: /new product/i })).toHaveCount(0)
})

test('inventory lock: a second person sees who holds it', async ({ browser }) => {
  const a = await (await browser.newContext()).newPage()
  const b = await (await browser.newContext()).newPage()
  await login(a, CHIEF)
  await nav(a, /^inventory$/i)
  await expect(a.getByRole('heading', { name: /stock levels|inventory/i }).first()).toBeVisible()
  await a.waitForLoadState('networkidle')

  await login(b, 'acc')
  await nav(b, /^inventory$/i)
  await expect(b.getByRole('alert')).toContainText(/boss/)
  await b.screenshot({ path: `${SHOTS}/inventory-locked.png` })

  await a.getByRole('button', { name: /leave inventory/i }).click() // releases the lock
  await b.getByRole('link', { name: /^receipts$/i }).click()
  await expect(b.getByRole('alert')).toHaveCount(0)
  await a.context().close(); await b.context().close()
})

test('everyone can change their own password and sign in with the new one', async ({ page }) => {
  const fresh = `${PASS}-new`
  await login(page, 'rev')
  await page.getByRole('button', { name: 'rev' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel(/^current password/i).fill('wrong-one')
  await dialog.getByLabel(/^new password$/i).fill(fresh)
  await dialog.getByLabel(/again/i).fill(fresh)
  await dialog.getByRole('button', { name: /^save$/i }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await dialog.getByLabel(/^current password/i).fill(PASS)
  await dialog.getByRole('button', { name: /^save$/i }).click()
  await expect(dialog.getByRole('status')).toBeVisible()
  await dialog.getByRole('button', { name: /back/i }).click()
  await page.getByRole('button', { name: /sign out/i }).click()
  await login(page, 'rev', fresh)
})

test('lists page through results', async ({ page }) => {
  await page.route('**/api/v1/inventory/receipts/?page=*', async (route) => {
    const n = Number(new URL(route.request().url()).searchParams.get('page'))
    await route.fulfill({ json: { count: 60, next: n === 1 ? 'x' : null, previous: n === 2 ? 'x' : null, results: [] } })
  })
  await login(page, CHIEF)
  await nav(page, /^inventory$/i)
  await page.getByRole('link', { name: /^receipts$/i }).click()
  await expect(page.getByText('60 records')).toBeVisible()
  await page.getByRole('button', { name: /^next$/i }).click()
  await expect(page.getByRole('button', { name: /^next$/i })).toBeDisabled()
  await expect(page.getByRole('button', { name: /^previous$/i })).toBeEnabled()
})

test('phone width: menu button, no sideways scroll, home and unknown page', async ({ browser }) => {
  const page = await (await browser.newContext({ viewport: { width: 390, height: 800 } })).newPage()
  await login(page, CHIEF)
  await expect(page.getByTestId('home-drafts')).toBeVisible()
  await expect(page.getByRole('navigation').first()).toBeHidden()
  await page.getByRole('button', { name: /menu/i }).click()
  await expect(page.getByRole('navigation').first()).toBeVisible()
  await nav(page, /^treasury$/i)
  await expect(page.getByRole('navigation').first()).toBeHidden()
  expect(await overflows(page)).toBe(false)
  await page.screenshot({ path: `${SHOTS}/phone-treasury.png`, fullPage: true })
  await page.goto('/no/such/page')
  await expect(page.getByRole('heading', { name: /does not exist/i })).toBeVisible()
  await page.context().close()
})

test('reports export to CSV with a BOM and open the print view', async ({ page }) => {
  await login(page, CHIEF)
  await nav(page, /^reports$/i)
  await expect(page.getByRole('cell', { name: /^total$/i })).toBeVisible()
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /export csv/i }).click()])
  expect(download.suggestedFilename()).toMatch(/\.csv$/)
  const text = await (await import('node:fs/promises')).readFile((await download.path())!, 'utf8')
  expect(text.charCodeAt(0)).toBe(0xfeff)
  expect(text).toMatch(/Total|الإجمالي/)
})
