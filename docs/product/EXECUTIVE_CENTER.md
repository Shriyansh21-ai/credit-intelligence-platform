# Executive Intelligence Center (M11)

Persona-tailored executive dashboards under `/api/fin/executive`, persisted to
`fin_exec_dashboards`. Each dashboard aggregates the deterministic outputs of the
other Track-3 engines into persona-relevant KPIs, an AI-generated executive
summary and strategic recommendations.

## Endpoints

| Path | Method |
|------|--------|
| `/personas` | the 10 supported personas + labels |
| `/dashboard` | build a persona dashboard |
| `/list`, `/{id}` | history + detail |

## Personas

CEO · CFO · CRO / Chief Risk Officer · Treasurer · Portfolio Manager · Board
Member · Credit Committee · Regulator · Relationship Manager.

## Grounded snapshot

A single `_platform_snapshot` reads every headline metric once — total EAD,
expected loss, weighted-avg PD, watchlist share, treasury KPIs, the Basel/IFRS 9
dashboard, portfolio ESG and market sentiment — grounded in the live exposure set.

Each persona view then selects the KPIs, sections and recommendations relevant to
that role. For example:

- **CEO / Board** — book size, EL rate, capital adequacy, ESG, market mood.
- **CFO** — NIM, funding cost, stable-funding ratio, expected loss.
- **CRO / Credit Committee** — weighted-avg PD, RWA, watchlist, Stage 3 names.
- **Treasurer** — total funding, blended cost, concentration, wholesale reliance.
- **Regulator** — CAR, RWA, provision coverage, lifetime ECL.

## Grounding-first summaries

The executive summary phrases the computed snapshot (book size, EL rate,
watchlist share, market mood) — it never invents figures. The dashboard stores a
checksum of the snapshot so the numbers behind the narrative are auditable.
```
