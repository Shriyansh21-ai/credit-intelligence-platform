# Simulation Engine (M9 Quantitative Risk)

Advanced quantitative models under `/api/fin/quant`, persisted to
`fin_risk_simulations`. Everything uses stdlib-only math from `common.py` and a
**seedable SplitMix64 RNG**, so every simulation is exactly reproducible across
machines and test runs (verified: identical seed → identical VaR).

## Endpoints

| Path | Method |
|------|--------|
| `/montecarlo` | correlated-factor P&L simulation (Cholesky) → VaR, ES, percentiles |
| `/var` | Value-at-Risk (parametric / historical / supplied returns), multi-day scaling |
| `/stress` | named factor-shock scenarios → worst-case P&L |
| `/sensitivity` | per-factor deltas and dominant factor |
| `/scenario-tree` | recombining binomial tree → terminal distribution & expectation |
| `/attribution` | component VaR (marginal contributions via covariance) |
| `/correlation` | correlation matrix + strongest pair |
| `/volatility` | EWMA (RiskMetrics λ=0.94) + sample vol, annualized |
| `/tail` | tail VaR/ES, tail ratio, skew & excess kurtosis, fat-tail flag |
| `/list`, `/{id}` | history + detail |

## Methods

- **Monte Carlo** — correlations imposed by a Cholesky factor L of the
  correlation matrix; each iteration draws standard normals, correlates them,
  and aggregates position P&L. VaR = percentile of the loss distribution; ES =
  mean of losses beyond VaR.
- **Parametric VaR** = (−μ + z·σ)·√horizon; closed-form **ES** = −μ + σ·φ(z)/(1−c).
- **Component VaR** — marginal VaRᵢ = z·Σⱼ wⱼ·covᵢⱼ / σ_p; contribution = wᵢ·marginalᵢ,
  summing to total VaR.
- **Scenario tree** — binomial with up/down moves and up-probability; node
  probabilities via the binomial coefficient; expectation over terminal nodes.
- **EWMA volatility** — σ²ₜ = λσ²ₜ₋₁ + (1−λ)r²ₜ, annualized by √252.

## Reproducibility & governance

Each simulation stores its seed, iterations, inputs and a result checksum. Given
the same seed and inputs the output is bit-identical, satisfying model-risk
reproducibility requirements.

## M15 validation

The M15 validation step runs the full backend test suite (existing baseline +
52 new Track 3 tests), verifies the Alembic migration upgrade/downgrade, and
confirms zero regressions. See `FINANCIAL_INTELLIGENCE_REPORT.md` for the test
summary.
```
