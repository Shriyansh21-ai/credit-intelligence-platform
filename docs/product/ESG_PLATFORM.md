# ESG Platform (M5 Climate & ESG Intelligence)

Enterprise ESG analytics under `/api/fin/esg`, persisted to
`fin_esg_assessments`. Deterministic scoring grounded in industry emission
factors and company profile signals.

## Endpoints

| Path | Method |
|------|--------|
| `/assess` | full E/S/G assessment + carbon exposure + recommendations |
| `/climate-stress` | carbon-price transition stress → cost & margin impact |
| `/portfolio` | exposure-weighted portfolio ESG + high-transition share |
| `/list` | assessment history |

## Scoring

- **Environmental** — inverse of the industry's transition + physical exposure.
- **Governance** — mapped from the company's credit rating (AAA→92 … CCC→35).
- **Social** — from employee base and years in business.
- **ESG score** = 0.4·E + 0.3·S + 0.3·G, banded AAA→B.

Industry emission factors (`INDUSTRY_EMISSIONS`) give carbon intensity (tCO₂e per
INR mn revenue), transition risk and physical risk per sector (energy, cement,
steel, manufacturing, transport, agriculture, technology, financial, …).

## Climate stress testing

A carbon-price shock (default 3× a baseline INR 3,000/tCO₂e) applied to estimated
carbon tonnes yields the incremental cost and margin impact, with a severity band
driven by the industry's transition exposure.

## Green financing & sustainable lending

`green_financing_eligible` is set when environmental score ≥ 60 and transition
risk < 0.5; a `sustainable_lending_signal` (positive/neutral/negative) is derived
from the overall ESG score. The engine emits concrete ESG recommendations
(emissions targets, decarbonisation capex covenants, governance strengthening).

## Portfolio ESG

`/portfolio` aggregates ESG across the live exposure set (exposure-weighted score)
and reports the share of EAD in high-transition industries — a climate-risk
concentration metric for the CRO and regulator dashboards.
```
