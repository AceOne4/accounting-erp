# Invoicing and VAT for the Egyptian market - design

Date: 2026-11-25. Status: draft for approval. Extends the existing `accounting-erp` repo
(Django API + React); nothing is rewritten.

## Intent and why

The product is meant to become a SaaS "short version" accounting system for small and
medium companies in Egypt. The owner's idea is a faster, cloud-hosted system with an AI
agent added later. Today the system has accounting, treasury and inventory but **no
invoices and no VAT**, so sales and expenses must be typed as raw journal entries. In
Egypt invoices are the centre of a company's books and are legally regulated: VAT-registered
businesses must issue invoices electronically through the Egyptian Tax Authority (ETA),
standard VAT is 14% (5% for production machinery), VAT returns are monthly, and only
ETA-registered e-documents count as support for input VAT. This design adds the invoice
layer first. The owner picked approach A: **compliance first, AI later**.

## Goals

1. Sales invoices, purchase invoices and credit notes (sales and purchase), per company,
   that post through the existing journal rules.
2. Correct VAT on every line (14% default, 5%, 0%/exempt via the existing product fields),
   and a monthly VAT report (output minus input).
3. Customer and supplier balances that follow invoices and payments: payments recorded in
   treasury can be matched to invoices; an open-invoices and ageing report.
4. Goods lines move stock and cost of sales automatically.
5. A printable invoice in Arabic and English.
6. A data model ready for ETA e-invoicing (phase 3) so it never has to be rebuilt.

## Non-goals (for this design)

- The ETA connection itself (clearance, signing, QR, portal sync): phase 3, designed for
  but not built. It depends on things outside the code: ETA registration, a signing
  certificate and ETA test-environment access.
- The AI agent. Not now; later it will call the same services this adds.
- Point-of-sale and e-receipts for shoppers (B2C), payroll, fixed assets, bank reconciliation.
- Multiple currencies and discounts beyond a simple per-line discount.
- Subscription billing, sign-up and hosting for the SaaS itself.

## Anti-goals (a failure even if it technically works)

- A VAT figure that differs by a piaster between the screen, the printed invoice, the journal
  entry and the VAT report.
- A posted invoice that can be edited or deleted, or an invoice and its journal entry that
  disagree.
- Anything that lets one company see or touch another company's invoices.
- Stock or cost-of-sales that silently stop matching the ledger.

## Constraints

- Existing stack and conventions stay: Django services hold all rules, the API only calls
  them; money is `Decimal` in Python and a string in JSON; every table is company-owned;
  OpenAPI schema and generated TypeScript types are regenerated; Arabic is the default
  language and every user-facing backend string needs an Arabic translation
  (`scripts/make_messages.py --check` runs in CI); Playwright covers new screens.
- Posted journal entries are immutable. Invoices follow the same rule.
- Egyptian rules used as facts (verified July 2026 by third-party guides, to be re-verified
  against the ETA before phase 3): standard VAT 14%, reduced 5%, monthly returns, 5-year
  archiving, digital signature required.

## Approaches considered

| | Build first | Trade-off |
|---|---|---|
| **A. Compliance first (chosen by the owner)** | Invoices, VAT, then ETA e-invoicing; AI later | Safest and needed by every VAT-registered customer; looks like competitors |
| B. AI first | Document upload to draft entries on the current system | Most distinctive; the agent would have little to act on (no invoices, VAT, bank data) |
| C. Thin core then AI | Basic invoices and VAT, then AI drafts, ETA after | Gets AI sooner; breaks if first customers must issue ETA e-invoices to stay legal |

The assistant had recommended C; the owner chose A. The first phase is identical in all
three, so the choice only affects what follows it: under A, ETA comes before AI.

## Design

### Data model (new app `sales`, or `invoicing`; name left to the builder)

- **CompanyTaxProfile** (one per company): tax registration number, commercial register
  number, address, default VAT rate (14.00), ETA branch/activity codes (nullable, used in
  phase 3).
- **Invoice**: company, kind (`sales`, `purchase`, `sales_credit`, `purchase_credit`),
  number (per company and kind, gap-free, same sequence mechanism as receipts), date,
  due date, partner (customer or supplier), status (`draft`, `posted`, `cancelled`-by-credit-note
  only), currency (EGP only for now), totals (net, VAT, gross), link to the journal entry it
  created, link to the invoice it corrects (credit notes), supplier's own invoice number
  and date (purchase), notes. ETA fields reserved and empty: document UUID, submission
  status, submitted-at, signed payload.
- **InvoiceLine**: product (optional; services have none), description, quantity, unit price,
  discount %, VAT rate (copied from the product or the company default at entry and then
  frozen on the line), warehouse (goods lines), computed line net, line VAT, line gross.
- **InvoiceSettlement**: links a treasury voucher entry (or any posted entry line on the
  customer/supplier account) to an invoice with an amount, so open balances are exact.

### Calculation rules (one function, used everywhere)

Line net = quantity x unit price x (1 - discount), rounded half-up to 2 decimals; line VAT =
line net x rate, rounded half-up to 2 decimals; invoice totals are sums of the rounded line
figures. The same function feeds the screen preview, the API, the journal entry, the printout
and the VAT report, and is unit-tested with awkward values. (Rounding mode is the owner's
call to confirm with an Egyptian accountant; see "Decisions for the owner".)

### Posting rules

- Sales invoice: DR customers 102 (gross) / CR sales 401 or service revenue 403 (net) /
  CR VAT output 203. Goods lines also consume FIFO stock in the chosen warehouse and post
  DR cost of goods sold 501 / CR inventory 105 at the FIFO cost.
- Purchase invoice: DR inventory 105, purchases 502 or expense account (net) / DR VAT input
  106 / CR suppliers 201 (gross). When the goods were already received through a stock
  receipt, the invoice clears goods-received-not-invoiced 210 instead of debiting inventory
  again, so stock is never counted twice.
- Credit notes reverse the relevant parts (sales returns 402 / purchase returns 503) and
  return stock at the original cost.
- An invoice posts its journal entry in the same transaction as the invoice's own status
  change. The entry is marked with `source="invoice"`; it cannot be edited or deleted from
  the journal screens (same link-lock as receipts).
- Posting is a separate, permissioned step from saving a draft, as for journal entries.

### Reports and screens

- Invoice list and form (draft, post, print; credit-note action from a posted invoice),
  customer/supplier open-invoices and ageing report, VAT report by month (output, input,
  net payable, with drill-down to invoices), company tax settings screen. Existing
  treasury "collect" and "pay supplier" vouchers gain "apply to invoices".
- Printable invoice in Arabic (RTL) and English, with the company tax number, partner tax
  number, line VAT and totals; a QR placeholder reserved for phase 3.
- Roles: accountant drafts; reviewer and chief post; chief deletes drafts; permission names
  follow the existing `invoice.*` style. System admin manages tax settings. (Owner to
  confirm.)

### Phasing

1. Sales and purchase invoices, VAT calculation, posting, print, link to stock. Credit notes.
2. Settlements, open-invoices and ageing report, monthly VAT report.
3. ETA e-invoicing: needs ETA registration, a signing certificate and test access first.
   Prerequisite research: ETA's current document schema and signing rules.

Every phase ends with backend tests (Postgres and SQLite), Playwright tests including
Arabic, regenerated schema and types, and a README update.

## Resolved from the builder check (assistant's calls; owner may overrule)

**Stock and purchases**
- Perpetual inventory: goods always go through 105 and cost of sales 501. Account 502
  (Purchases) is used only for non-stock lines that are expensed, and for price variances
  (below).
- A purchase-invoice line may reference a stock-receipt line. A receipt line can be invoiced
  partly or by several invoices; the invoiced quantity is tracked per receipt line. An
  invoice posting clears 210 for the referenced receipt value.
- Price difference between invoice and receipt: the FIFO layer is not revalued in this
  version; the difference posts to 502 and is listed in the VAT/purchases report as a
  variance. (Revaluing layers is a later improvement.)
- A goods line with no receipt: posting the invoice creates its own stock receipt and FIFO
  layer (the line needs a warehouse), so stock and ledger never diverge.
- A receipt that has been invoiced is locked against edits and deletion, like a receipt
  whose stock was used.

**Sales and credit notes**
- New stock-move types `sale` and `sale_return`, owned by the invoice, consuming FIFO layers
  through the existing machinery.
- Credit note for goods must link to the original invoice; the credited quantity per line is
  capped by what was invoiced minus earlier credits, and stock returns at the original
  consumption cost. A price-only credit (allowance, no goods back) is allowed and has no
  stock effect. A credit note without a link is allowed only for services lines.
- Posting a full credit note does not cancel the original. There is no `cancelled` status;
  an invoice shows its credited amount. VAT month follows each document's own date, so
  the reversal lands in the credit note's month.

**Accounts and tax categories**
- Product gets a `kind` (goods or service). Sales lines post to 401 for goods and 403 for
  services by default; each line may override with another leaf account of the company.
  Purchase lines: stock goods go to 105; any other line must carry an expense or asset
  account chosen by the user (e.g. 113 for machinery).
- Each line carries a tax category (`standard` 14%, `reduced` 5%, `zero`, `exempt`) and
  the rate is frozen on the line. The VAT report separates the four categories.

**VAT report and settlements**
- The VAT report is ledger-based (sums of 203 and 106 by month) with drill-down to invoices;
  anything posted to those accounts by manual journals is shown as a separate
  "not from invoices" line so the difference is visible instead of hidden. Net payable may be
  negative (a credit); no automatic carry-forward. The VAT payment entry is a manual journal
  in this version.
- Settlements: entries already on 102/201 that are not matched to invoices (opening balances,
  old raw entries) show as "unallocated" so the ageing total always equals the ledger. A
  voucher can be applied to invoices at creation or afterwards, but only once posted.
- Sales invoice to a business partner requires the partner's tax number when the company is
  VAT-registered (company tax profile has the registration number).
- Purchase invoices are not blocked for lacking an ETA document (phase 3 adds a flag).

## Decisions for the owner

1. **Negative stock.** Block posting a sales invoice when stock is short (default), or allow
   it and cost it later? Blocking is simple and safe; allowing it suits businesses that invoice
   before booking receipts but needs a costing fallback.
2. **Withholding tax** (deduction by corporate customers). Out of scope by default. If it is
   needed, settlements need a deduction concept from the start.
3. **ETA timing and customer type.** Defaults: first customers are B2B, goods and services,
   and none must issue ETA e-invoices at launch. If any must, phase 3 moves up and the
   external prerequisites (registration, signing certificate, test access) must start now.
4. Cheap to change later, defaults stand unless you object: VAT rounding per line half-up,
   and invoices are posted by reviewer and chief only.

## Left to the builder

Names of apps, tables and endpoints; screen layout; exact print template; test data;
how the open-invoice matching handles part payments and overpayments; migration steps.
