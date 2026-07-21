"""Portfolio risk intelligence (Phase 4, Milestone 6).

Aggregates individual enterprise assessments into portfolio-level intelligence:
portfolio health, exposure and expected/unexpected loss, distributions by
industry / rating / region, concentration (HHI), and the top risk clients.

The aggregation math is a pure function of a list of positions
(:func:`analyze`), so it is fully unit-testable; the repository layer maps
persisted assessments into those positions.
"""

from .portfolio_intelligence import Position, analyze, position_from_assessment  # noqa: F401
