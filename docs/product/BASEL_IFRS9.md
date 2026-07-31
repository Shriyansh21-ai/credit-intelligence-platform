# Basel III / IFRS 9 Platform (M3)

Explainable enterprise regulatory calculations under `/api/fin/regulatory`.
Every result stores `results`, an `explanation` (formula + inputs + whether it
was grounded on a real company profile), and a checksum in `fin_regulatory_calcs`.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/ecl` | 12-month & lifetime ECL, staging, provisioning |
| POST | `/rwa` | IRB or standardized Risk-Weighted Assets |
| POST | `/car` | capital adequacy ratios vs Basel minimums |
| POST | `/leverage` | Basel III leverage ratio |
| GET | `/dashboard` | consolidated Basel + IFRS 9 over live exposures |
| GET | `/calcs`, `/calcs/{id}` | history + full detail |

## IFRS 9

- **PD/LGD/EAD** resolved from the company profile (grounded) or supplied.
- **12-month ECL** = PD₁₂ × LGD × EAD.
- **Lifetime ECL** = Σₜ [marginal_PDₜ × LGD × EAD / (1+EIR)ᵗ] using a
  survival-based marginal PD term structure.
- **Staging** — Stage 1 (performing), Stage 2 (SICR: 30+ dpd, PD more than
  doubled vs origination, or absolute PD ≥ 20%), Stage 3 (90+ dpd, credit-
  impaired). Provision = 12m ECL for Stage 1, lifetime ECL for Stage 2/3.

## Basel III

- **IRB RWA** — Vasicek capital requirement K with the supervisory asset
  correlation R(PD) and maturity adjustment b(PD): conditional PD at the 99.9%
  confidence level, K = (LGD·condPD − PD·LGD)·maturity_adj, RWA = K × 12.5 × EAD.
- **Standardized RWA** = risk_weight(external rating) × EAD.
- **CAR** — CET1/RWA, Tier1/RWA, Total/RWA vs minimums incl. the 2.5% capital
  conservation buffer (CET1 ≥ 7%, Tier1 ≥ 8.5%, Total ≥ 10.5%).
- **Leverage ratio** = Tier 1 / total exposure ≥ 3%.

## Explainability

Every response includes the exact formula, the inputs used and a
`grounded_on_profile` flag. Combined with the stored checksum, calculations are
fully auditable and reproducible for model-risk governance and regulatory review.
```
