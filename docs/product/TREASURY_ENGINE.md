# Treasury Engine (M1)

A deterministic treasury analytics engine under `/api/fin/treasury`. All outputs
persist to `fin_treasury_snapshots` and carry a `grounding` block (facts +
checksum). Funding sources are held in `fin_funding_sources`.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/source-types` | funding types + liquidity bucket keys |
| GET/POST | `/funding-sources` | list / register a funding source |
| POST | `/cash-position` | aggregate cash & liquid assets |
| POST | `/liquidity-buckets` | ladder assets/liabilities into maturity buckets, gaps |
| POST | `/funding-gap` | available vs stable funding against a need |
| POST | `/nim` | net interest margin vs blended funding cost |
| POST | `/yield` | weighted-avg yield & duration |
| POST | `/alm` | ALM gap report with rate-shock EVE impact |
| POST | `/lcr` | Basel Liquidity Coverage Ratio |
| POST | `/nsfr` | Basel Net Stable Funding Ratio |
| POST | `/cash-forecast` | projected cash path with ± bands |
| POST | `/scenario` | liquidity shock scenarios (LCR under each) |
| POST | `/stress` | liquidity survival horizon under stress |
| POST | `/funding-optimization` | greedy least-cost funding mix |
| GET | `/kpis`, `/dashboard`, `/snapshots` | KPIs, command view, history |

## Key formulas

- **NIM** = (earning_assets × asset_yield − total_funding × blended_cost) / earning_assets.
- **LCR** = HQLA / max(net 30-day outflows, 25% of gross); inflows capped at 75%
  of outflows (Basel). Run-off factors per funding type (deposit 10%, wholesale
  75%, interbank 100%, …).
- **NSFR** = Available Stable Funding / Required Stable Funding; ASF weights per
  funding type (deposit 0.90, wholesale 0.50, bond 1.0, …).
- **ALM/EVE** — buckets ranked by maturity; EVE impact ≈ Σ −gap × shock ×
  bucket-mid-duration; balance sheet flagged asset- or liability-sensitive.
- **Funding optimization** — sources sorted by rate ascending, drawn to target;
  reports blended cost, blended stability and feasibility vs a stability floor.

## Historical & projected data

Every computation is stored as a snapshot with `kind` (cash|liquidity|alm|lcr|
nsfr|forecast|scenario|kpis|yield) and `as_of`, so treasury reporting spans
historical positions and projected paths. The dashboard returns the latest
snapshot per kind plus live KPIs.
```
