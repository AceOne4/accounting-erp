import { expect, test, type Page } from '@playwright/test'

const PASS = process.env.E2E_PASS ?? ''
const CHIEF = process.env.E2E_USER ?? ''
const ADMIN = process.env.E2E_ADMIN ?? ''
if (!PASS || !CHIEF || !ADMIN) throw new Error('Set E2E_USER (chief accountant), E2E_ADMIN (system admin) and E2E_PASS')
const SHOTS = process.env.E2E_SHOTS ?? 'e2e/shots'

test.describe.configure({ mode: 'serial' })

async function login(page: Page, user: string) {
  await page.goto('/')
  await page.getByLabel(/username|اسم المستخدم/i).fill(user)
  await page.getByLabel(/password|كلمة المرور/i).fill(PASS)
  await page.getByRole('button', { name: /sign in|تسجيل الدخول/i }).click()
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr')
}
const nav = (page: Page, name: RegExp) => page.getByRole('navigation').first().getByRole('link', { name }).click()

test('customers and suppliers, and the chart of accounts', async ({ page }) => {
  await login(page, CHIEF)
  await nav(page, /customers & suppliers/i)
  for (const [name, kind] of [['Al Nour', 'Customer'], ['Delta Supplies', 'Supplier']]) {
    await page.getByRole('button', { name: /new customer/i }).click()
    await page.getByLabel(/^name$/i).fill(name)
    await page.getByLabel(/^type/i).selectOption({ label: kind })
    await page.getByRole('button', { name: /^save$/i }).click()
    await expect(page.getByRole('cell', { name })).toBeVisible()
  }
  await page.screenshot({ path: `${SHOTS}/10-partners.png` })

  await nav(page, /chart of accounts/i)
  await expect(page.getByText('1011').first()).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/11-accounts.png` })
})

test('treasury: fund, collect from a customer, post, then count the box', async ({ page }) => {
  await login(page, CHIEF)
  await nav(page, /^treasury$/i)
  await expect(page.getByTestId('book-1011')).toHaveText('0.00')

  await page.getByLabel(/^operation/i).selectOption({ label: 'Fund the expenses box' })
  await page.getByLabel(/^amount$/i).fill('1000.00')
  await page.getByLabel(/post immediately/i).check()
  await page.getByRole('button', { name: /^save$/i }).first().click()
  await expect(page.getByRole('status').filter({ hasText: /posted/i })).toBeVisible()
  await expect(page.getByTestId('book-1011')).toHaveText('1,000.00')

  await page.getByLabel(/^operation/i).selectOption({ label: 'Collect from customer' })
  await page.getByLabel(/customer \/ supplier/i).selectOption({ label: 'Al Nour' })
  await page.getByLabel(/^amount$/i).fill('300.00')
  await page.getByRole('button', { name: /^save$/i }).first().click()
  await expect(page.getByRole('status').filter({ hasText: /draft/i })).toBeVisible()

  // count 4 x 200 + 1 x 100 = 900 against a book balance of 1,000
  await page.getByLabel(/^box$/i).selectOption({ index: 0 })
  await page.getByLabel(/denomination 200/i).fill('4')
  await page.getByLabel(/denomination 100/i).fill('1')
  await expect(page.getByTestId('counted-total')).toHaveText('900.00')
  await expect(page.getByTestId('count-diff')).toHaveText('-100.00')
  await page.getByRole('button', { name: /save count/i }).click()
  await expect(page.getByRole('status').filter({ hasText: /count saved/i })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/12-treasury.png`, fullPage: true })
})

test('inventory: setup, receipts, transfer, over-transfer rejected, stock count', async ({ page }) => {
  await login(page, CHIEF)
  await nav(page, /^inventory$/i)
  await page.getByRole('link', { name: /^setup$/i }).click()

  await page.getByRole('textbox', { name: /^name$/i }).last().fill('Piece') // unit form is last on the page
  await page.getByRole('button', { name: /^add$/i }).last().click()
  await expect(page.getByRole('listitem').filter({ hasText: 'Piece' })).toBeVisible()
  for (const [code, name] of [['MAIN', 'Main'], ['B2', 'Branch']]) {
    await page.getByRole('textbox', { name: /^code$/i }).fill(code)
    await page.getByRole('textbox', { name: /^name$/i }).first().fill(name)
    await page.getByRole('button', { name: /^add$/i }).first().click()
    await expect(page.getByRole('listitem').filter({ hasText: code })).toBeVisible()
  }
  await page.getByRole('button', { name: /new product/i }).click()
  const product = page.locator('form').filter({ hasText: /tax rate/i })
  await product.getByLabel(/^code$/i).fill('W1')
  await product.getByLabel(/^name$/i).fill('Widget')
  await product.getByLabel(/^unit$/i).selectOption({ label: 'Piece' })
  await product.getByRole('button', { name: /^save$/i }).click()
  await expect(page.getByRole('cell', { name: /Widget/ })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/13-inventory-setup.png`, fullPage: true })

  // two receipts: 10 @ 1 and 10 @ 5
  for (const cost of ['1', '5']) {
    await page.getByRole('link', { name: /^receipts$/i }).click()
    await page.getByRole('link', { name: /new receipt/i }).click()
    await page.getByLabel(/^warehouse$/i).selectOption({ label: 'MAIN' })
    await page.getByLabel(/^supplier$/i).selectOption({ label: 'Delta Supplies' })
    await page.getByLabel(/^product$/i).selectOption({ index: 1 })
    await page.getByLabel(/^quantity$/i).fill('10')
    await page.getByLabel(/unit cost/i).fill(cost)
    await page.getByRole('button', { name: /^save$/i }).click()
    await expect(page).toHaveURL(/\/inventory\/receipts$/)
  }
  await expect(page.getByRole('link', { name: /RC-0000\d/ })).toHaveCount(2)

  // transfer 15 MAIN -> B2, then an impossible 99
  await page.getByRole('link', { name: /^transfers$/i }).click()
  await page.getByRole('link', { name: /new transfer/i }).click()
  await page.getByLabel(/^from$/i).selectOption({ label: 'MAIN' })
  await page.getByLabel(/^to$/i).selectOption({ label: 'B2' })
  await page.getByLabel(/^product$/i).selectOption({ index: 1 })
  await page.getByLabel(/^quantity$/i).fill('99')
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByLabel(/^quantity$/i).fill('15')
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page).toHaveURL(/\/inventory\/transfers$/)

  // FIFO: 10 @ 1 + 5 @ 5 = 35 moved, 5 @ 5 = 25 left behind; total 10 + 50 = 60
  await page.getByRole('link', { name: /^stock levels$/i }).click()
  await expect(page.getByTestId('levels-total')).toHaveText('60.00')
  await page.screenshot({ path: `${SHOTS}/14-stock-levels.png`, fullPage: true })

  await page.getByRole('link', { name: /^stock counts$/i }).click()
  await page.getByRole('link', { name: /new stock count/i }).click()
  await page.getByLabel(/^warehouse$/i).selectOption({ label: 'B2' })
  await page.getByLabel(/^product$/i).selectOption({ index: 1 })
  await page.getByLabel(/^quantity$/i).fill('14')
  await page.getByRole('button', { name: /^save$/i }).click()
  await expect(page.getByRole('heading', { name: /count CNT-/i })).toBeVisible()
  await expect(page.getByRole('cell', { name: '-1', exact: true })).toBeVisible()
})

test('reports: trial balance balances; ledger and statement open', async ({ page }) => {
  await login(page, CHIEF)
  await nav(page, /^reports$/i)
  await expect(page.getByRole('cell', { name: /^1011/ })).toBeVisible()
  await expect(page.getByText(/not balanced/i)).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/15-trial-balance.png`, fullPage: true })
  await page.getByRole('link', { name: /account ledger/i }).click()
  await expect(page.getByText(/choose an account/i)).toBeVisible()
  await page.getByRole('link', { name: /statement/i }).click()
  await expect(page.getByText(/choose a customer or supplier/i)).toBeVisible()
})

test('users: only an admin sees the screen and can add a member', async ({ page }) => {
  await login(page, CHIEF)
  await expect(page.getByRole('navigation').first().getByRole('link', { name: /^users$/i })).toHaveCount(0)
  await page.getByRole('button', { name: /sign out/i }).click()

  await login(page, ADMIN)
  await nav(page, /^users$/i)
  await page.getByRole('button', { name: /add user/i }).click()
  const form = page.locator('form')
  await form.getByLabel(/^username$/i).fill('newhire')
  await form.getByLabel(/^password$/i).fill(PASS)
  await form.getByLabel(/^role/i).selectOption({ label: 'Accountant' })
  await form.getByRole('button', { name: /^save$/i }).click()
  await expect(page.getByRole('cell', { name: 'newhire' })).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/16-users.png` })
  await expect(page.getByRole('combobox', { name: 'Role' }).filter({ has: page.locator('option:checked', { hasText: 'System admin' }) })).toBeDisabled() // cannot change your own access
})
