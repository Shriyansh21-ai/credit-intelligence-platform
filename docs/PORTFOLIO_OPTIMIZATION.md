# Portfolio Optimization (M2 + M12)

Portfolio intelligence (`/api/fin/portfolio`) and the decision-optimization
engine (`/api/fin/optimize`) together provide construction, analytics and
optimization for commercial/SME/corporate loan books.

## Portfolio analytics (M2)

Positions live in `fin_portfolio_positions`; every analysis persists to
`fin_portfolio_analyses` with a grounding block.

| Endpoint | Method |
|----------|--------|
| `/{id}/summary` | EAD, EL, UL, weighted-avg PD/maturity, rating distribution |
| `/{id}/concentration` | sector/geo/region HHI + Gini, single-largest %, top-N, industry×region heatmap |
| `/{id}/loss` | Vasicek analytic credit VaR at 99.9% + economic capital |
| `/{id}/raroc` | revenue − EL − opex over economic capital; EVA; value-creation flag |
| `/{id}/simulate` | Monte-Carlo single-factor default simulation → loss VaR/ES/percentiles |
| `/{id}/migration` | annual rating transition matrix → projected default flow |
| `/{id}/ews` | early-warning watchlist by PD, rating, concentration |
| `/{id}/insights` | composite grounded AI insight |
| `/{id}/sync` | populate from the live per-company exposure set |

### Loss model

- **Expected Loss** = Σ PDᵢ·LGDᵢ·EADᵢ.
- **Unexpected Loss** — single-name UL = EAD·LGD·√(PD(1−PD)); portfolio UL uses
  the Basel IRB asset correlation R(PD) to blend pairwise contributions.
- **Credit VaR** — Vasicek conditional PD at the confidence level, summed to a
  tail loss; economic capital = VaR − EL.
- **Simulation** — seedable single-factor Gaussian copula; each name defaults
  when its latent asset return falls below the PD threshold.

## Decision optimization (M12)

All optimizers return a `solution` plus an `explanation` (objective, binding
constraint, trade-off) and persist to `fin_optimizations`.

| Endpoint | Method |
|----------|--------|
| `/loan-pricing` | risk-based rate = CoF + PD·LGD + opex + capital_ratio·target_RoE |
| `/credit-limit` | min(single-name cap × capital, EL budget / (PD·LGD)) |
| `/portfolio-allocation` | greedy RAROC allocation under a per-name max weight |
| `/capital-allocation` | RAROC×demand weighting capped at stated demand |
| `/collateral` | cheapest-first collateral mix after haircuts to cover exposure |

### Concentration optimization

`/{id}/optimize` (M2) trims names above the single-name limit and scales sectors
above the sector limit, reporting freed capital and the HHI improvement — an
explainable, deterministic rebalancing plan.
```
