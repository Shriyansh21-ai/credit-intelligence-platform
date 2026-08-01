"""Enterprise stress testing.

Banking-style stress testing. Each named macro scenario (recession, high
inflation, rate shock, ...) is expressed as a bundle of scenario adjustments at
three severities. The engine produces the four regulatory cases — Base
Optimistic, Expected and Worst — plus per-scenario detail and comparison series
(PD / expected loss / score / health / recommendation) ready for charting.

Built entirely on the deterministic scenario engine, so stress
results are reproducible and explainable.
"""

from .scenarios import STRESS_SCENARIOS, available_scenarios  # noqa: F401
from .stress_engine import run_stress_test  # noqa: F401
