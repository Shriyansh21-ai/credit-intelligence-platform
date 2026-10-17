# Customer Portfolio Import

The portfolio import workflow accepts customer-owned CSV and XLSX files. It is
separate from the demo portfolio loader and does not create a credit decision.

## Run locally and migrate

From the repository root, install backend dependencies, configure the local
environment, apply migrations, and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m uvicorn backend.app.main:app --reload
```

In another terminal, start the frontend:

```powershell
cd frontend
bun install
bun run dev
```

The browser API origin defaults to `http://127.0.0.1:8000`. Configure
`VITE_API_URL` in `frontend/.env` if the API is hosted elsewhere. The database
defaults to SQLite. For PostgreSQL, set `DATABASE_URL` to a PostgreSQL DSN
using the installed psycopg driver, then run `alembic upgrade head` against
that database before starting the API.

## Import a portfolio

1. Sign in and open **Portfolio File Import** from the Banking Ecosystem section.
2. Upload a `.csv` or `.xlsx` file. XLSX inspection lists visible worksheets;
   choose the worksheet to map.
3. Review deterministic header-alias suggestions and map at least one source
   column to Company name. Unused source columns can be ignored.
4. Validate and inspect the row preview, findings, and validation counts.
5. Select the explicit confirmation checkbox and confirm. Existing tenant
   company identities are skipped; the importer does not update existing rows.
6. Review the result and import history. Download the tenant-protected CSV
   validation report when needed.

No write occurs at upload or validation time. Imports are synchronous and
bounded to 5,000 rows by default. A failed database transaction does not leave
partially imported company records. Repeating a completed confirmation returns
the recorded result without repeating writes.

## File limits and validation

`MAX_UPLOAD_MB` controls the upload byte limit. `PORTFOLIO_IMPORT_MAX_ROWS`
defaults to 5,000 and `PORTFOLIO_IMPORT_MAX_COLUMNS` defaults to 100. XLSX
archives are checked for excessive expanded size, compression ratio, member
count, and encrypted entries before parsing. Macros are unsupported; formula
cells in mapped fields are rejected rather than evaluated. Duplicate or blank
headers, malformed records, unsupported extensions, and invalid workbook
content are rejected. Filenames are reduced to a safe display name and never
used as a storage path.

Canonical destinations currently supported:

| Destination | Notes |
| --- | --- |
| Company name | Required for every row. |
| External company ID | Optional; if absent, a stable hash of the normalized company name is used. |
| Industry, country | Industry defaults to `Unclassified` with a warning; country is optional. |
| Currency | Required when a monetary value is supplied; must be a recognized ISO 4217 code. |
| Financial reporting year | Required when financial statement amounts are supplied. |
| Annual revenue, revenue, EBITDA, net income | Amounts map to existing company/financial fields. |
| Total assets, total liabilities, current assets, current liabilities, debt, cash, operating cash flow | Stored on the existing financial statement row for the mapped reporting year. |
| Total exposure, outstanding principal, requested loan amount, interest rate, days past due | Stored only in matching existing exposure/credit fields; interest rate is expressed as a percentage from 0 to 100. |

Amounts are parsed with decimal arithmetic, non-finite and out-of-range values
are rejected, and ambiguous number grouping is not accepted. The existing
company financial, credit, and exposure tables use SQL floating-point columns;
conversion at persistence can lose decimal precision. Do not use these values
as an accounting ledger until those legacy columns are migrated to an explicit
fixed-precision decimal type. Currency is stored on the company record, so one
company import row represents a single reporting currency; conversion is not
performed.

Errors prevent a row from importing. Warnings (such as a missing industry or
duplicate identity) remain visible; duplicate identities are skipped by the
default policy. Validation reports include row, field, code, severity, and
message, but omit source cell contents.

## Persistence, tenant isolation, and analysis

The backend resolves tenant identity from the authenticated user and checks
`portfolio.view` or `portfolio.manage`; tenant IDs supplied by the browser
are ignored. New self-service signups get isolated organizations. Sharing
requires an explicit tenant membership, not a matching email domain. Existing
memberships are preserved.

Source rows are temporarily staged in the database while the import awaits
mapping/confirmation. They are cleared after completion, cancellation, or
failure; history retains metadata and validation findings, not the source
values. There is no background worker for this bounded workflow.

Imported company records are marked `is_demo=false` and
`data_source=customer_csv_import`. Demo records remain separately labelled.
The importer does not run or invent credit scores, approve/reject loans, or
trigger an unsupported analysis. Existing score-analysis integration, company
detail browsing, and manual company creation are not part of this import slice.

CSV/XLSX file import is available. Financial-document processing and external
accounting, banking, and bureau data connectors are not established by this
workflow and require their own configured, authorized integrations.

## Synthetic template

[`portfolio-import-template.csv`](portfolio-import-template.csv) contains
synthetic records only. Replace them with an appropriately authorized customer
export, map the source headers, and inspect all validation warnings before
confirmation.