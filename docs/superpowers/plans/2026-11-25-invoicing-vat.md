# Invoicing and VAT Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sales/purchase invoices, credit notes, VAT, payment matching, ageing and a monthly VAT report to the existing `accounting-erp` repo (phases 1 and 2 of the spec).

**Architecture:** A new Django app `sales` holds invoice models and services. Posting an invoice runs in one transaction: stock moves (existing FIFO code), then a journal entry created with `source="invoice"` and posted through the existing `accounting.services`. The API only calls services. The React app gets invoice screens and report tabs next to the existing ones.

**Tech Stack:** Django 6.1 + DRF + drf-spectacular + simple-history, PostgreSQL (SQLite for tests), React 19 + TanStack Query + i18next + decimal.js, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-25-invoicing-vat-design.md` (phase 3, ETA e-invoicing, is NOT in this plan: it needs its own spec after the owner has ETA registration, a signing certificate and test access).

## Global Constraints

- Rules live in services; the API only calls them. Money is `Decimal` in Python and a string in JSON. Every table is company-owned (`core.CompanyOwned`).
- Posted journal entries and posted invoices are immutable; corrections go through credit notes. Invoices post their entry with `source="invoice"` (link-locked like receipts).
- VAT: standard 14.00%, reduced 5.00%, zero 0.00%, exempt 0.00%; per line, rounded half-up to 2 decimals (`ROUND_HALF_UP`); invoice totals are sums of rounded line figures.
- Accounts (existing chart): 102 customers, 201 suppliers, 105 inventory, 210 goods received not invoiced, 106 VAT input, 203 VAT output, 401 sales, 402 sales returns, 403 service revenue, 501 cost of goods sold, 502 purchases, 503 purchase returns.
- Block a sales invoice when stock is short (existing `consume_fifo` raises "Insufficient stock"). No withholding tax. First customers assumed B2B. EGP only.
- Every new user-facing backend string is wrapped in gettext and translated: `python scripts/make_messages.py --check` must pass. Regenerate `backend/schema.yml` and `npm run api:types` after any API change; `spectacular --fail-on-warn` must pass.
- Tests run on Postgres and on SQLite (`DJANGO_DB=sqlite`); `DJANGO_DEBUG=1` locally. conftest forces English.
- Document numbers per company and kind: `INV-`, `PINV-`, `CN-` (sales credit), `PCN-` (purchase credit) + 5 digits, via `inventory.models.next_number`.
- Commit messages end with the attribution lines from the session reminder.

## Review Focus

1. Tiny and half-cent amounts: price 0.03 at 14% gives VAT 0.00; 0.25 at 14% gives 0.04 (half-up). Pinned in Task 2.
2. Posting the same invoice twice or from two requests: the second must fail and stock must be consumed once. Pinned in Task 4.
3. Wrong partner kind (supplier on a sales invoice), inactive partner/product, no lines, zero gross total. Pinned in Task 3.
4. Company with no tax profile, or a business customer without a tax number, when posting a sales invoice: clear translated error, nothing posted. Pinned in Task 4.
5. Credit note over the invoiced quantity, credit of a draft invoice, second credit exhausting the first's remainder. Pinned in Task 6.

## File Structure

- Create `backend/sales/` : `models.py` (CompanyTaxProfile, Invoice, InvoiceLine, InvoiceSettlement), `tax.py` (pure VAT maths), `services.py` (draft CRUD, post), `credit.py` (credit notes), `settlements.py`, `reports.py` (ageing, VAT), `serializers.py`, `api.py`, `urls.py`, `tests/`.
- Modify `backend/inventory/models.py` (Product.kind, StockMove.DocType, ReceiptLine invoiced qty), `backend/inventory/services.py` (receipt lock), `backend/core/permissions.py`, `backend/config/settings.py`, `backend/config/urls.py`.
- Create frontend `src/pages/Invoices.tsx`, `InvoiceForm.tsx`, `InvoicePrint.tsx`, `TaxProfile.tsx`; modify `Reports.tsx`, `Treasury.tsx` (apply to invoices), `Shell.tsx`, `App.tsx`, locale files.

---

# Part A: Invoices (phase 1)

### Task 1: App scaffold, tax profile, product kind, permissions

**Files:**
- Create: `backend/sales/{__init__,apps,models,urls}.py`, `backend/sales/migrations/0001_initial.py`, `backend/sales/tests/{__init__,test_profile.py}`
- Modify: `backend/inventory/models.py` (+`Product.kind`), `backend/inventory/migrations/0003_product_kind.py`, `backend/core/permissions.py`, `backend/config/settings.py` (add `"sales"`), `backend/config/urls.py`

**Interfaces:**
- Produces: `sales.models.CompanyTaxProfile(company OneToOne, tax_registration_number, commercial_register, address, default_vat_rate=Decimal("14.00"), eta_branch_code="", eta_activity_code="")`; `inventory.models.Product.kind` in `{"goods","service"}` default `"goods"`; capabilities `invoice.view` (added to `VIEW`), `invoice.create`, `invoice.edit`, `invoice.post`, `invoice.delete`, `tax.manage`.
- Role map: accountant `view,create,edit`; reviewer `view,edit,post`; chief `view,create,edit,post,delete`; system admin `view,tax.manage`.

- [ ] **Step 1: Write failing tests** in `test_profile.py`: `test_profile_defaults_to_14_percent`, `test_role_capabilities` (assert accountant has `invoice.create` but not `invoice.post`; reviewer has `invoice.post` but not `invoice.create`; chief has `invoice.delete`; admin has `tax.manage`), `test_product_kind_defaults_to_goods`.
- [ ] **Step 2: Run** `pytest sales -v` — expect FAIL (no app).
- [ ] **Step 3: Implement** the models, migrations (`makemigrations sales inventory`), capability entries and app wiring.
- [ ] **Step 4: Run** `pytest -q` — expect all pass; `python manage.py makemigrations --check --dry-run` clean.
- [ ] **Step 5: Commit** `feat(sales): app scaffold, tax profile, product kind, invoice capabilities`.

### Task 2: VAT calculation module

**Files:** Create `backend/sales/tax.py`, `backend/sales/tests/test_tax.py`.

**Interfaces:**
- Produces:
  - `RATES: dict[str, Decimal]` = `{"standard": Decimal("14.00"), "reduced": Decimal("5.00"), "zero": Decimal("0.00"), "exempt": Decimal("0.00")}`
  - `money(x: Decimal) -> Decimal` (2 dp, `ROUND_HALF_UP`)
  - `@dataclass(frozen=True) LineAmounts(net: Decimal, vat: Decimal, gross: Decimal)`
  - `line_amounts(quantity: Decimal, unit_price: Decimal, discount_pct: Decimal, rate: Decimal) -> LineAmounts`
  - `invoice_totals(lines: Iterable[LineAmounts]) -> LineAmounts`

- [ ] **Step 1: Write failing tests**: `line_amounts(Decimal("3"), Decimal("10.00"), Decimal("0"), Decimal("14.00")) == LineAmounts(Decimal("30.00"), Decimal("4.20"), Decimal("34.20"))`; 10% discount on 100.00 at 14% gives net 90.00, VAT 12.60; `(1, "0.03", 0, 14)` gives VAT `0.00`; `(1, "0.25", 0, 14)` gives VAT `0.04`; totals of three lines equal the sum of their rounded parts (not the rounded sum of raw parts); a hypothesis-free table test of 5 awkward values.
- [ ] **Step 2: Run** `pytest sales/tests/test_tax.py -v` — expect FAIL.
- [ ] **Step 3: Implement** the functions in `tax.py`; discount applies before VAT; net rounded first, VAT computed from the rounded net.
- [ ] **Step 4: Run** the same command — expect PASS.
- [ ] **Step 5: Commit** `feat(sales): VAT calculation`.

### Task 3: Invoice models and draft services

**Files:** Create `backend/sales/models.py` additions (Invoice, InvoiceLine), migration `0002_invoice.py`, `backend/sales/services.py`, `backend/sales/tests/test_drafts.py`.

**Interfaces:**
- Consumes: `tax.line_amounts`, `tax.RATES`, `inventory.models.next_number`.
- Produces:
  - `Invoice(NumberedMixin, CompanyOwned)` fields: `kind` (`sales|purchase|sales_credit|purchase_credit`), `number`, `date`, `due_date` null, `partner` FK, `status` (`draft|posted`), `supplier_invoice_number`, `supplier_invoice_date` null, `original` FK self null, `net_total`, `vat_total`, `gross_total`, `journal_entry` FK null, `notes`, `created_by`, reserved `eta_uuid`, `eta_status`, `eta_submitted_at`, `eta_payload` (JSON), history. The prefix comes from kind (`INV`, `PINV`, `CN`, `PCN`).
  - `InvoiceLine` fields: `invoice` FK, `product` FK null, `description`, `quantity`, `unit_price`, `discount_pct`, `tax_category`, `vat_rate`, `warehouse` FK null, `account` FK null, `receipt_line` FK null, `original_line` FK null, `net`, `vat`, `gross`.
  - `@dataclass(frozen=True) InvoiceLineInput(product, description, quantity, unit_price, discount_pct=Decimal("0"), tax_category=None, warehouse=None, account=None, receipt_line=None, original_line=None)`
  - `create_invoice(*, company, user, kind, date, partner, lines, due_date=None, supplier_invoice_number="", supplier_invoice_date=None, original=None, notes="") -> Invoice`
  - `update_invoice(*, invoice, date, partner, lines, due_date=None, supplier_invoice_number="", supplier_invoice_date=None, notes="") -> Invoice` (draft only)
  - `delete_invoice(*, invoice) -> None` (draft only)
  - `default_tax_category(company, product) -> str`: `exempt` if `product.tax_exempt`; else by `product.tax_rate`: null or the company default gives `standard`, `5` gives `reduced`, `0` gives `zero`; any other rate raises `ValidationError`.

- [ ] **Step 1: Write failing tests** in `test_drafts.py`: `test_create_sales_invoice_computes_totals` (2 lines: 3 x 10.00 standard and 1 x 100.00 reduced give net 130.00, VAT 9.20, gross 139.20, number `INV-00001`); `test_numbers_are_per_company_and_kind`; `test_vat_rate_is_frozen_on_the_line` (change company default after creating, line keeps its rate); `test_supplier_on_sales_invoice_rejected`; `test_inactive_partner_or_product_rejected`; `test_no_lines_rejected`; `test_zero_gross_rejected_at_save`; `test_foreign_company_product_rejected`; `test_update_and_delete_only_while_draft`.
- [ ] **Step 2: Run** `pytest sales/tests/test_drafts.py -v` — expect FAIL.
- [ ] **Step 3: Implement** models + migration + services; validation messages in gettext; a goods line (product kind goods) in a sales invoice requires `warehouse`; a service line must not have one.
- [ ] **Step 4: Run** the file — expect PASS; then `makemigrations --check`.
- [ ] **Step 5: Commit** `feat(sales): invoice models and draft services`.

### Task 4: Post a sales invoice (revenue, VAT, stock, cost of sales)

**Files:** Modify `backend/inventory/models.py` (`StockMove.DocType` += `SALE="sale"`, `SALE_RETURN="sale_return"`, `PURCHASE_RETURN="purchase_return"`) + migration `0004_stockmove_doctypes.py`; modify `backend/sales/services.py`; create `backend/sales/tests/test_post_sales.py`.

**Interfaces:**
- Consumes: `accounting.services.create_entry/post_entry`, `LineInput`, `inventory.services.consume_fifo`.
- Produces: `post_invoice(*, invoice, user) -> Invoice` (this task handles `kind="sales"`; later tasks extend the same function). The whole call is `@transaction.atomic`, starts with `select_for_update()` on the invoice, and raises `ValidationError` if the status is not draft.
- Entry for a sales invoice: `DR 102 (partner) gross / CR line account net per line (401 goods, 403 service, or line.account) / CR 203 vat`; per goods line one `StockMove(doc_type="sale", quantity=-qty, value=-cost)` and `DR 501 cost / CR 105 cost`. The entry uses `source="invoice"`, is posted with `post_entry`, and the invoice stores `journal_entry` and `status="posted"`.
- Pre-checks (before any write): company has a `CompanyTaxProfile` with a registration number, and the partner has `tax_id`, else a translated `ValidationError`.

- [ ] **Step 1: Write failing tests** in `test_post_sales.py`: `test_post_sales_invoice_entries` (receipt of 10 @ 6.00 exists; invoice 10 x 100.00 standard: entry lines `102 DR 1140.00`, `401 CR 1000.00`, `203 CR 140.00`, `501 DR 60.00`, `105 CR 60.00`; entry `status=="posted"`, `source=="invoice"`); `test_stock_is_consumed_once_and_fifo` (two layers 6.00 and 8.00, sell 15, cost = 10 x 6 + 5 x 8 = 100.00); `test_insufficient_stock_blocks_and_rolls_back` (nothing posted, stock unchanged); `test_post_twice_fails` (second call raises, `available_qty` unchanged); `test_posted_invoice_cannot_be_edited_or_deleted`; `test_invoice_entry_cannot_be_edited_from_journal` (`accounting.update_entry` without `allow_linked` raises); `test_missing_tax_profile_blocks_post`; `test_business_customer_without_tax_id_blocks_post`; `test_service_line_posts_to_403`; `test_line_account_override`.
- [ ] **Step 2: Run** `pytest sales/tests/test_post_sales.py -v` — expect FAIL.
- [ ] **Step 3: Implement** `post_invoice` for sales; build lines with the existing `LineInput`; reuse the `money` helper from `inventory.services`; sum stock cost per product before posting COGS lines.
- [ ] **Step 4: Run** the file and then `pytest -q` — expect PASS.
- [ ] **Step 5: Commit** `feat(sales): post sales invoices with VAT, stock and cost of sales`.

### Task 5: Post a purchase invoice (receipts, GRNI, variance)

**Files:** Modify `backend/inventory/models.py` (`StockReceiptLine.invoiced_qty`, default 0) + migration `0005_receiptline_invoiced_qty.py`; modify `backend/inventory/services.py` (`receipt_lock_reason` returns a translated reason when any line has `invoiced_qty > 0`); modify `backend/sales/services.py`; create `backend/sales/tests/test_post_purchase.py`.

**Interfaces:**
- Consumes: `inventory.services.create_receipt`, `ReceiptLineInput`, `accounting.services`.
- Extends `post_invoice` for `kind="purchase"`: for each stock-goods line, if `receipt_line` is set, check `quantity <= receipt_line.quantity - receipt_line.invoiced_qty`; if not set, create (inside the same transaction) one receipt for the invoice's goods lines with their warehouse and unit price, post its entry (`accounting.post_entry`), and use the new receipt lines. Then `invoiced_qty += quantity`.
- Entry: `DR 210 (receipt value) / DR 502 variance (invoice net minus receipt value, when positive; CR 502 when negative) / DR expense or asset account per non-stock line / DR 106 vat / CR 201 (partner) gross`, `source="invoice"`, posted. Non-stock lines need `account` (error otherwise).
- Receipt value for a partly invoiced line = `quantity x receipt unit cost` (layer `unit_cost`).

- [ ] **Step 1: Write failing tests**: `test_invoice_against_receipt_clears_210` (receipt 10 @ 50.00 posted; invoice 10 @ 50.00: `210 DR 500.00`, `106 DR 70.00`, `201 CR 570.00`); `test_price_difference_goes_to_502` (invoice @ 55.00: `210 DR 500.00`, `502 DR 50.00`, `106 DR 77.00`, `201 CR 627.00`; FIFO layer cost still 50.00); `test_partial_and_second_invoice` (invoice 4, then 6, third attempt for 1 fails); `test_goods_without_receipt_creates_receipt_and_layer` (stock 10 appears, ledger 105 equals stock value); `test_invoiced_receipt_is_locked` (`update_receipt` raises); `test_non_stock_line_needs_account`; `test_expense_line_with_5_percent_asset` (line account 113, reduced category, VAT 5%).
- [ ] **Step 2: Run** `pytest sales/tests/test_post_purchase.py -v` — expect FAIL.
- [ ] **Step 3: Implement** as described; variance never revalues the layer.
- [ ] **Step 4: Run** `pytest -q` — expect PASS (including existing inventory tests).
- [ ] **Step 5: Commit** `feat(sales): post purchase invoices against receipts`.

### Task 6: Credit notes

**Files:** Create `backend/sales/credit.py`, `backend/sales/tests/test_credit.py`; modify `backend/sales/services.py` (`post_invoice` dispatches credit kinds to `credit.py`).

**Interfaces:**
- Produces: `create_credit_note(*, user, original: Invoice, date, lines: list[InvoiceLineInput], notes="") -> Invoice`; kind is derived (`sales` gives `sales_credit`, `purchase` gives `purchase_credit`); the original must be posted. `credited_quantity(original_line: InvoiceLine) -> Decimal` (sum over posted credit lines).
- Rules: goods lines must set `original_line` and a quantity `<= original_line.quantity - credited_quantity(original_line)`; services lines may omit `original_line`; a price-only credit sets quantity with `product` of kind goods and `warehouse=None` plus `description`, and has no stock effect only when the line is flagged `price_only` (add boolean `InvoiceLine.price_only`, default False, in this task's migration; Task 3 lines default it to False).
- Sales credit entry: `DR 402 net / DR 203 vat / CR 102 gross`; returned goods: new layer at the original average consumption cost (`StockMove sale_return`), `DR 105 / CR 501` at that cost. Purchase credit entry: `DR 201 gross / CR 106 vat / CR 105 at the FIFO cost of the returned stock (StockMove purchase_return) / CR 503 for (net - stock cost), or DR 503 when that difference is negative`; non-stock lines credit their own account.

- [ ] **Step 1: Write failing tests**: `test_sales_credit_returns_stock_at_original_cost` (sold 10 at cost 6.00; credit 4: stock +4 at 6.00, `105 DR 24.00`, `501 CR 24.00`, `402 DR` net, `203 DR` vat, `102 CR` gross); `test_credit_over_quantity_rejected`; `test_second_credit_limited_to_remainder` (10 sold, credit 6 ok, credit 5 fails, credit 4 ok); `test_credit_of_draft_invoice_rejected`; `test_service_credit_without_link_allowed`; `test_price_only_credit_has_no_stock_effect`; `test_purchase_credit_reduces_stock_and_201`; `test_original_is_not_cancelled`.
- [ ] **Step 2: Run** `pytest sales/tests/test_credit.py -v` — expect FAIL.
- [ ] **Step 3: Implement**; add the `price_only` field + migration `0003`.
- [ ] **Step 4: Run** `pytest -q` — expect PASS.
- [ ] **Step 5: Commit** `feat(sales): credit notes with stock return`.

### Task 7: Invoice API and schema

**Files:** Create `backend/sales/{serializers,api,urls}.py`, `backend/sales/tests/test_api.py`; modify `backend/config/urls.py`, `backend/schema.yml`; update `frontend/src/api/generated`.

**Interfaces:**
- Produces endpoints under `/api/v1/sales/`: `invoices/` (list with `?kind=&status=&partner=&q=`, create, retrieve, update PUT, destroy), `invoices/{id}/post/` (POST), `invoices/{id}/credit/` (POST body = credit lines), `tax-profile/` (GET, PUT).
- Capability map: list/retrieve `invoice.view`; create `invoice.create`; update `invoice.edit`; post `invoice.post`; destroy `invoice.delete`; credit `invoice.create`; tax profile GET `invoice.view`, PUT `tax.manage`. Use `CapabilityMixin` and `SaveInCompany` like `inventory.api`.
- Serializer exposes `lines`, totals, `status`, `journal_entry`, `credited_amount`, and read-only `locked_reason`.

- [ ] **Step 1: Write failing API tests**: `test_accountant_creates_but_cannot_post` (201 then 403), `test_reviewer_posts` (200, status posted), `test_tenancy` (other company's invoice returns 404), `test_post_validation_errors_are_translated` (Arabic message with `Accept-Language: ar`), `test_list_filters`, `test_logged_out_is_401`, `test_tax_profile_permissions`.
- [ ] **Step 2: Run** `pytest sales/tests/test_api.py -v` — expect FAIL.
- [ ] **Step 3: Implement**, then `python scripts/make_messages.py` (fill Arabic in `locale/ar/LC_MESSAGES/django.po`), `python manage.py spectacular --file schema.yml --fail-on-warn`, `cd ../frontend && npm run api:types`.
- [ ] **Step 4: Run** `pytest -q`, `python scripts/make_messages.py --check`, `npx tsc -b` — all pass.
- [ ] **Step 5: Commit** `feat(sales): invoice API`.

### Task 8: Invoice screens, tax settings, printable invoice

**Files:** Create `frontend/src/pages/{Invoices,InvoiceForm,InvoicePrint,TaxProfile}.tsx`, `frontend/src/vat.ts` (+`vat.test.ts`), `frontend/e2e/invoices.spec.ts`; modify `App.tsx`, `Shell.tsx`, `src/locales/{en,ar}.json`.

**Interfaces:**
- `vat.ts`: `lineAmounts(quantity: string, unitPrice: string, discountPct: string, rate: string): { net: string; vat: string; gross: string }` using decimal.js `ROUND_HALF_UP`, matching `sales/tax.py` exactly; tested against the same five values as Task 2 (`30.00/4.20/34.20`, `90.00/12.60`, VAT `0.00` for 0.03, `0.04` for 0.25).
- Routes: `/invoices` (list, tabs for sales, purchase, credit), `/invoices/new?kind=`, `/invoices/:id`, `/invoices/:id/print`, `/settings/tax` (visible with `tax.manage`). Nav item "Invoices" (needs `invoice.view`).
- Form: product picker fills price/category/warehouse default; live totals via `vat.ts`; Post button only with `invoice.post` and unchanged form; posted invoices read-only with a "Create credit note" button; link to the journal entry; Print opens `/invoices/:id/print` (A4 layout, company tax number, partner tax number, lines with VAT, totals, reserved QR box) and calls `window.print()`.

- [ ] **Step 1: Write failing tests**: `vat.test.ts` as above; Playwright `invoices.spec.ts`: `sales invoice: draft, post, totals match print` (company profile saved, customer with tax number, product with stock, invoice 2 x 100.00 standard shows `228.00`, post as chief, journal entry shows `source` locked, print page shows `228.00`); `purchase invoice against receipt`; `credit note from posted invoice`; `accountant cannot post`; `Arabic screens fit width and show no untranslated keys` (reuse the `leakedKey`/`overflows` checks from `e2e/extras.spec.ts` for `/invoices`, `/invoices/new`, a print page, `/settings/tax`).
- [ ] **Step 2: Run** `npx vitest run src/vat.test.ts` — expect FAIL.
- [ ] **Step 3: Implement** `vat.ts`, then screens and locale keys (en and ar); lazy-load the invoice pages like the other screens.
- [ ] **Step 4: Run** `npx tsc -b && npm run lint && npx vitest run && npm run build`, reseed the e2e database and `npx playwright test` (see README) — expect all pass.
- [ ] **Step 5: Commit** `feat(web): invoices, tax settings, printable invoice`.

---

# Part B: Settlements, ageing, VAT report (phase 2)

### Task 9: Settlements (match payments to invoices)

**Files:** Add `InvoiceSettlement` to `backend/sales/models.py` + migration; create `backend/sales/settlements.py`, `backend/sales/tests/test_settlements.py`; modify `backend/treasury/api.py` and `backend/treasury/services.py` only to accept an optional `apply_to` list on `VoucherView` posts.

**Interfaces:**
- `InvoiceSettlement(company, invoice FK, entry FK to a posted JournalEntry, amount, created_by, created_at)`.
- `settle(*, invoice, entry, amount, user) -> InvoiceSettlement`: entry must be posted, belong to the same company and have a line on the invoice's partner account (102 for sales, 201 for purchase) with the right side (credit for customer payment, debit for supplier payment); the amount must not exceed the entry's unallocated part nor the invoice's open balance.
- `open_balance(invoice) -> Decimal` = gross minus settlements minus posted credit notes (credit notes of the invoice reduce it).
- Voucher API: `apply_to: [{"invoice": id, "amount": "..."}]`, allowed only with `post_now` true or applied later through `POST /sales/invoices/{id}/settle/` once the entry is posted.

- [ ] **Step 1: Write failing tests**: `test_collect_voucher_settles_invoice` (invoice 1140.00, collect 500.00: balance 640.00); `test_over_settlement_rejected`; `test_draft_voucher_cannot_be_applied`; `test_settling_wrong_partner_or_side_rejected`; `test_credit_note_reduces_open_balance`; `test_one_payment_across_two_invoices`.
- [ ] **Step 2: Run** `pytest sales/tests/test_settlements.py -v` — expect FAIL.
- [ ] **Step 3: Implement**, regenerate schema/types and translations.
- [ ] **Step 4: Run** `pytest -q`, `make_messages --check`, `npx tsc -b` — all pass.
- [ ] **Step 5: Commit** `feat(sales): settlements`.

### Task 10: Open-invoices / ageing and VAT reports (API)

**Files:** Create `backend/sales/reports.py`, `backend/sales/tests/test_reports.py`; modify `sales/api.py`, `sales/urls.py`.

**Interfaces:**
- `ageing(company, kind: str, as_of: date) -> dict` with rows per partner `{partner, current, d1_30, d31_60, d61_90, over_90, unallocated, total}` (buckets by days past `due_date`, or `date` when null), where `unallocated` = partner's ledger balance on 102/201 minus open invoice balances (opening and legacy entries), so the grand total equals the ledger balance.
- `vat_report(company, year: int, month: int) -> dict` = ledger-based: `output` (sum of credits minus debits on 203 for posted entries dated in the month), `input` (106), `net_payable = output - input` (may be negative), per category (`standard, reduced, zero, exempt`) net and VAT from posted invoices, and `not_from_invoices` (203/106 movements whose entry `source != "invoice"`).
- Endpoints `GET /sales/reports/ageing/?kind=sales|purchase&as_of=` and `GET /sales/reports/vat/?year=&month=` (capability `reports.view`).

- [ ] **Step 1: Write failing tests**: `test_ageing_buckets` (invoice due 45 days ago in `d31_60`); `test_ageing_total_equals_ledger_with_legacy_entry` (a raw journal entry on 102 shows as `unallocated`); `test_vat_report_month_boundaries` (invoice on the 31st and one on the 1st land in different months; a credit note dated next month reduces that month); `test_vat_report_separates_categories`; `test_manual_vat_journal_is_reported_separately`; `test_negative_net_payable`.
- [ ] **Step 2: Run** `pytest sales/tests/test_reports.py -v` — expect FAIL.
- [ ] **Step 3: Implement**; regenerate schema and types.
- [ ] **Step 4: Run** `pytest -q` and the schema checks — pass.
- [ ] **Step 5: Commit** `feat(sales): ageing and VAT reports`.

### Task 11: Phase 2 screens, README, final verification

**Files:** Modify `frontend/src/pages/{Reports,Treasury,InvoiceForm}.tsx`, locale files, `README.md`, `.github/workflows/ci.yml` (no change expected); create `frontend/e2e/phase2.spec.ts`, `scripts/e2e-reset.sh` (recreates the e2e database and test users `boss`, `sysadmin`, `acc`, `rev` as the README describes).

- [ ] **Step 1: Write failing Playwright tests**: `collect from customer and apply to an invoice` (open balance falls on the invoice form); `ageing report total equals customer ledger`; `VAT report for the month shows output 140.00 after a 1000.00 sale`; `Arabic and phone-width checks for the new report tabs and the apply-to-invoices panel`.
- [ ] **Step 2: Run** `npx playwright test e2e/phase2.spec.ts` — expect FAIL.
- [ ] **Step 3: Implement** report tabs (ageing for sales and purchase, VAT month picker, Print and CSV like the existing reports), the apply-to-invoices panel on treasury collect/supplier vouchers, locale keys, README sections (invoices, VAT rules, settlements, e2e script).
- [ ] **Step 4: Run the full verification**: backend `pytest -q` on Postgres and SQLite, `makemigrations --check --dry-run`, `make_messages.py --check`, `spectacular --fail-on-warn` with an unchanged `schema.yml`, frontend `npx tsc -b`, `npm run lint` (zero warnings), `npx vitest run`, `npm run build`, and `npx playwright test` twice from a freshly reset database — all pass.
- [ ] **Step 5: Commit and push** `feat: settlements, ageing, VAT report screens`; check GitHub Actions for the commit.
