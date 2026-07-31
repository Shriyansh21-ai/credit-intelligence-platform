# Strategic Intelligence Platform (M14)

Enterprise strategic reports under `/api/fin/strategic`, persisted to
`fin_strategic_reports`. Each report **combines deterministic analytics with AI
reasoning while preserving citations and evidence** — every section names the
source engine and the checksum of the result it was built from.

## Endpoints

| Path | Method |
|------|--------|
| `/types` | the 9 report types |
| `/generate` | generate a report |
| `/list`, `/{id}` | history + detail |

## Report types

executive_briefing · market · industry · competitor · economic · regulatory ·
portfolio · investment · outlook.

## Composition

The generator assembles sections from the other Track-3 engines:

- **Company sections** (competitor/investment reports) — benchmarking (M10),
  a revenue forecast (M8) and an ESG assessment (M5) for the subject.
- **Platform sections** — the Basel/IFRS 9 dashboard (M3), an adverse macro
  propagation (M4) and market sentiment (M6).
- **Executive briefings** additionally lead with the CEO executive dashboard
  (M11) summary.

Each section carries an `evidence` object (`source`, `checksum`, `generated_at`)
and the `facts` it is grounded on. Recommendations are synthesised across
sections and an explicit long-term outlook is appended.

## Grounding & auditability

Consistent with the Track 2 grounding-first design, AI reasoning only phrases the
deterministic facts; it never sources numbers. The full report stores a checksum
over its sections and citations, so any report is reproducible and every claim
traces back to a specific engine result — meeting the evidence and citation
requirements for board- and regulator-facing intelligence.
```
