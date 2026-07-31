# Financial Digital Twin (M13)

Driver-based digital twins under `/api/fin/twin`, stored in `fin_twins` with
simulations in `fin_twin_simulations`. A twin models a real entity whose `state`
(named metrics) evolves under `drivers` (growth/decay rates); simulating it
projects the state forward under an optional scenario of driver shocks.

## Endpoints

| Path | Method |
|------|--------|
| `/types` | the 9 twin types |
| `POST /` | create a twin (seeds state/drivers from the company profile when linked) |
| `GET /` , `/{id}` | list / detail |
| `/{id}/update` | patch state/drivers |
| `/{id}/simulate` | project forward under a scenario |
| `/{id}/simulations` | simulation history |

## Twin types

company · industry · portfolio · economy · bank · treasury · market ·
supply_chain · counterparty. A `company` twin seeds revenue, margin, ratios and
PD from the linked assessment; an `economy` twin seeds GDP, inflation,
unemployment and the policy rate.

## Simulation

Each metric compounds per period by `(driver_rate + scenario_shock)`. Risk-like
metrics (PD, CAR, LCR, NSFR, margin) are bounded to sane ranges. The output is a
period-by-period `path`, the `terminal_state` and the `deltas` from the initial
state, plus a grounding block and checksum.

Example: a company twin with a `{"revenue": -0.10}` scenario shock produces a
lower terminal revenue than the unshocked baseline — used for what-if business
outcome analysis.

## Integration

Twins integrate with the **Economic Scenario Engine (M4)** — a propagated macro
scenario's driver shocks can be fed directly into `simulate` — and feed the
**Strategic Intelligence Platform (M14)**, where twin outcomes become report
evidence. This lets the platform simulate future business outcomes for a company,
portfolio, bank, treasury, market or the wider economy within the existing AI
workflows.
```
