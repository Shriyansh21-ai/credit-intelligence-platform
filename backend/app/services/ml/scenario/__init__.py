"""Scenario simulation (Phase 4, Milestone 4).

Interactive "what-if" analysis. A scenario is a set of adjustments (revenue down
20%, +2pp interest rate, customer loss, ...) applied to an assessment's inputs;
the engine recomputes the full risk picture — score, PD, expected loss, health,
recommendation, loan sizing and pricing — and reports the delta against the
baseline.

Adjustments are pure functions of the inputs, so the same engine drives both
single what-if analysis today and Monte-Carlo sampling later (see
:func:`scenario_engine.simulate_many`).
"""

from .scenario_engine import (  # noqa: F401
    available_factors,
    simulate,
    simulate_many,
)
