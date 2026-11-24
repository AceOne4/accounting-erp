import { expect, test, type Page } from '@playwright/test'

const USER = process.env.E2E_USER ?? ''
const PASS = process.env.E2E_PASS ?? ''
if (!USER || !PASS) throw new Error('Set E2E_USER and E2E_PASS (a chief accountant of the seeded company)')
const SHOTS = process.env.E2E_SHOTS ?? 'e2e/shots'

async function login(page: Page) {
  await page.goto('/')
  await page.getByLabel(/username|اسم المستخدم/i).fill(USER)
  await page.getByLabel(/password|كلمة المرور/i).fill(PASS)
  await page.getByRole('button', { name: /sign in|تسجيل الدخول/i }).click()
}

test('wrong password shows an error and stays on login', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel(/username|اسم المستخدم/i).fill(USER)
  await page.getByLabel(/password|كلمة المرور/i).fill('definitely-wrong')
  await page.getByRole('button', { name: /sign in|تسجيل الدخول/i }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/01-login-error.png` })
})

test('create, balance-check, save, post and lock a journal entry', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('heading', { name: /قيود اليومية|journal entries/i })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await page.screenshot({ path: `${SHOTS}/02-list-ar.png` })

  await page.getByRole('link', { name: /قيد جديد|new entry/i }).click()
  await page.getByRole('textbox', { name: /البيان|description/i }).fill('E2E cash sale')

  const rows = page.locator('tbody tr')
  const first = rows.nth(0)
  const second = rows.nth(1)
  await first.getByRole('combobox').first().selectOption({ index: 1 }) // 1011 expenses box
  await first.getByLabel(/مدين|debit/i).fill('250.00')
  await second.getByRole('combobox').first().selectOption({ index: 2 }) // 1012 collections box
  await second.getByLabel(/دائن|credit/i).fill('200.00')

  // unbalanced: totals show it and posting is not even offered yet (new entry)
  await expect(page.getByTestId('total-debit')).toHaveText('250.00')
  await expect(page.getByTestId('total-credit')).toHaveText('200.00')
  await expect(page.getByText(/الفرق|off by/i)).toBeVisible()
  await page.screenshot({ path: `${SHOTS}/03-unbalanced-ar.png` })

  await second.getByLabel(/دائن|credit/i).fill('250.00')
  await expect(page.getByText(/متوازن|balanced/i).first()).toBeVisible()
  await page.getByRole('button', { name: /حفظ كمسودة|save draft/i }).click()
  await expect(page).toHaveURL(/\/journal\/\d+$/)

  await page.getByRole('button', { name: /^ترحيل$|^post$/i }).click()
  await expect(page.getByText(/مرحّل ولا يمكن|posted and can no longer/i)).toBeVisible()
  await expect(page.getByRole('button', { name: /حفظ|save/i })).toHaveCount(0)
  await page.screenshot({ path: `${SHOTS}/04-posted-ar.png` })
})

test('English layout is left-to-right', async ({ page }) => {
  await login(page)
  await expect(page.getByRole('heading', { name: /قيود اليومية/ })).toBeVisible()
  await page.getByRole('button', { name: 'English' }).click()
  await expect(page.getByRole('heading', { name: /journal entries/i })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr')
  await page.screenshot({ path: `${SHOTS}/05-list-en.png` })
})
