# Forecasting Guide (M8)

Multi-horizon enterprise forecasting under `/api/fin/forecast`, persisted to
`fin_forecasts`. Every forecast returns a series of `{t, point, lower, upper}`
with 95% confidence intervals.

## Endpoints

| Path | Method |
|------|--------|
| `/types` | the 10 supported forecast types |
| `/run` | run a single forecast at a given horizon |
| `/multi-horizon` | the same forecast at several horizons (e.g. 3/6/12/24) |
| `/list`, `/{id}` | history + detail |

## Forecast types

revenue · cashflow · working_capital · profit · growth · industry · portfolio ·
risk · default · recovery. Each has type-specific default drift/vol used when no
history is supplied; a seed history is otherwise derived from the company
profile (`data_access`).

## Method — deterministic ensemble

Each step blends three views and averages them:

1. **Linear trend** — OLS fit of the history extrapolated.
2. **Damped trend** — trend with a 0.85 damping factor per step.
3. **Drift** — last value compounded at the type drift.

Confidence bands widen with the square root of the horizon:
`band = residual_vol·√h + |point|·type_vol·0.2`, and the interval is
`point ± 1.96·band`.

## Metrics

Each forecast reports the fitted slope, implied CAGR, terminal value and terminal
range. `multi_horizon` returns the terminal value and range per horizon for quick
comparison.

## Grounding

The forecast stores its input history and a result checksum; narratives phrase
the computed terminal value and interval — they never invent figures.
```
