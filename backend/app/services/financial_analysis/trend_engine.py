"""Financial Trend Engine (Task 3).

Multi-period analysis: year-over-year / quarter-over-quarter deltas and CAGR
across a chronological list of statements. The engine is deliberately built now
even though most borrowers currently have a single period — it degrades
gracefully (``direction="insufficient_data"`` with an empty delta list) and
becomes the input to future benchmarking and the ML risk engine without any
schema change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Sequence

from .primitives import Number, mean_ignoring_missing, pct_change
from .statement import FinancialStatement

# Metric extractors: (key, label, unit, extractor).
_METRICS: List[tuple] = [
    ("revenue", "Revenue", "currency", lambda s: s.revenue),
    ("gross_profit", "Gross Profit", "currency", lambda s: s.gross_profit_value),
    ("ebitda", "EBITDA", "currency", lambda s: s.ebitda),
    ("net_profit", "Net Profit", "currency", lambda s: s.net_profit),
    ("operating_cash_flow", "Operating Cash Flow", "currency", lambda s: s.operating_cash_flow),
    ("working_capital", "Working Capital", "currency", lambda s: s.working_capital),
    ("total_debt", "Total Debt", "currency", lambda s: s.total_debt),
    ("net_margin", "Net Margin", "percent",
     lambda s: (s.net_profit / s.revenue) if s.revenue not in (None, 0) and s.net_profit is not None else None),
]

# Metrics where a rising value is unfavourable (so direction is inverted).
_LOWER_IS_BETTER = {"total_debt"}

IMPROVING = "improving"
DECLINING = "declining"
STABLE = "stable"
INSUFFICIENT = "insufficient_data"

_STABLE_BAND = 0.02  # |avg change| < 2% reads as flat


@dataclass
class MetricTrend:
    key: str
    label: str
    unit: str
    series: List[dict]        # [{period, value}]
    changes: List[dict]       # consecutive period-over-period changes
    cagr: Number
    direction: str

    def as_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "series": self.series,
            "changes": self.changes,
            "cagr": None if self.cagr is None else round(self.cagr, 4),
            "direction": self.direction,
        }


def _cagr(first: Number, last: Number, periods: int) -> Number:
    if first is None or last is None or periods < 1 or first <= 0 or last <= 0:
        return None
    return (last / first) ** (1.0 / periods) - 1.0


def _direction(changes: Sequence[Number], key: str) -> str:
    values = [c for c in changes if c is not None]
    if not values:
        return INSUFFICIENT
    avg = mean_ignoring_missing(values)
    if avg is None or abs(avg) < _STABLE_BAND:
        return STABLE
    rising = avg > 0
    if key in _LOWER_IS_BETTER:
        rising = not rising
    return IMPROVING if rising else DECLINING


def _period_label(statement: FinancialStatement, index: int) -> str:
    return statement.period.label or (
        f"FY{statement.period.fiscal_year}" if statement.period.fiscal_year else f"Period {index + 1}"
    )


def _metric_trend(statements: Sequence[FinancialStatement], key, label, unit, extractor) -> MetricTrend:
    series = []
    values: List[Number] = []
    for i, s in enumerate(statements):
        value = extractor(s)
        values.append(value)
        series.append({"period": _period_label(s, i), "value": value})

    changes = []
    for i in range(1, len(statements)):
        change = pct_change(values[i], values[i - 1])
        changes.append({
            "from": _period_label(statements[i - 1], i - 1),
            "to": _period_label(statements[i], i),
            "change": None if change is None else round(change, 4),
        })

    cagr = _cagr(values[0], values[-1], len(statements) - 1) if len(statements) >= 2 else None
    direction = _direction([c["change"] for c in changes], key)
    return MetricTrend(key, label, unit, series, changes, cagr, direction)


def compute_trends(statements: Sequence[FinancialStatement]) -> dict:
    """Compute trends across an ordered list of statements (oldest first)."""
    ordered = sorted(
        statements,
        key=lambda s: (
            s.period.sequence if s.period.sequence is not None else (s.period.fiscal_year or 0)
        ),
    )
    metrics = {
        key: _metric_trend(ordered, key, label, unit, extractor).as_dict()
        for key, label, unit, extractor in _METRICS
    }

    period_count = len(ordered)
    if period_count < 2:
        summary = (
            "Only one reporting period is available; trends will populate once a "
            "second period is analysed."
        )
    else:
        rev = metrics["revenue"]
        if rev["cagr"] is not None:
            summary = (
                f"Across {period_count} periods, revenue is {rev['direction']} "
                f"({rev['cagr'] * 100:.1f}% CAGR)."
            )
        else:
            summary = f"Trends computed across {period_count} periods."

    return {
        "period_count": period_count,
        "periods": [_period_label(s, i) for i, s in enumerate(ordered)],
        "sufficient_data": period_count >= 2,
        "metrics": metrics,
        "summary": summary,
    }
