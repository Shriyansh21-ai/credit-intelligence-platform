"""M8 — Enterprise Forecasting Platform.

Multi-horizon forecasting for revenue, cash flow, working capital, profit
growth, industry, portfolio, risk, expected-default and recovery — always with
confidence intervals. Forecasts use a deterministic *ensemble* (linear trend
damped trend, and mean-reversion) over a supplied history, or derive a seed
history from the company profile when none is given. No external ML deps; every
band widens with the square-root of horizon.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import FinForecast
from . import data_access as da
from .common import (
    cagr, checksum, clamp, grounding_block, iso, mean, stdev, to_float, utcnow,
)

FORECAST_TYPES = ["revenue", "cashflow", "working_capital", "profit", "growth",
                  "industry", "portfolio", "risk", "default", "recovery"]

# Type-specific default drift/vol when no history is provided.
TYPE_DEFAULTS = {
    "revenue": {"drift": 0.08, "vol": 0.10}, "cashflow": {"drift": 0.06, "vol": 0.15},
    "working_capital": {"drift": 0.05, "vol": 0.12}, "profit": {"drift": 0.07, "vol": 0.18},
    "growth": {"drift": 0.0, "vol": 0.05}, "industry": {"drift": 0.06, "vol": 0.08},
    "portfolio": {"drift": 0.05, "vol": 0.10}, "risk": {"drift": 0.0, "vol": 0.08},
    "default": {"drift": 0.0, "vol": 0.06}, "recovery": {"drift": 0.0, "vol": 0.09},
}


def _fit_trend(history: List[float]) -> Dict[str, float]:
    """OLS linear fit on the history plus level/vol statistics."""
    n = len(history)
    if n == 0:
        return {"level": 0.0, "slope": 0.0, "vol": 0.0}
    if n == 1:
        return {"level": history[0], "slope": 0.0, "vol": abs(history[0]) * 0.1}
    xs = list(range(n))
    mx, my = mean(xs), mean(history)
    denom = sum((x - mx) ** 2 for x in xs) or 1.0
    slope = sum((xs[i] - mx) * (history[i] - my) for i in range(n)) / denom
    level = history[-1]
    residuals = [history[i] - (my + slope * (xs[i] - mx)) for i in range(n)]
    return {"level": level, "slope": slope, "vol": stdev(residuals) if n > 2 else abs(my) * 0.1}


def _ensemble_point(fit: Dict[str, float], drift: float, h: int, last: float) -> float:
    """Blend three views for step h: linear, damped trend, mean-reversion/drift."""
    linear = fit["level"] + fit["slope"] * h
    damped = fit["level"] + fit["slope"] * sum(0.85 ** k for k in range(h))
    drifted = last * ((1 + drift) ** h)
    return (linear + damped + drifted) / 3.0


def forecast(db: Session, *, forecast_type: str, subject_ref: Optional[str] = None,
             assessment_id: Optional[int] = None, horizon: int = 12,
             history: Optional[List[float]] = None, frequency: str = "monthly",
             drift: Optional[float] = None, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None) -> Dict[str, Any]:
    if forecast_type not in FORECAST_TYPES:
        raise ValueError(f"unknown forecast_type '{forecast_type}'")
    defaults = TYPE_DEFAULTS.get(forecast_type, {"drift": 0.05, "vol": 0.10})
    prof = None
    if not history and (subject_ref or assessment_id):
        prof = da.company_or_none(db, assessment_id=assessment_id, company_ref=subject_ref)
    if not history:
        ei = (prof or {}).get("engine_input", {}) if prof else {}
        seed = to_float(ei.get("revenue") if forecast_type == "revenue" else
                        ei.get("operating_cash_flow") if forecast_type == "cashflow" else
                        ei.get("net_margin") if forecast_type in ("profit", "growth") else None,
                        100.0)
        d = defaults["drift"] if drift is None else drift
        history = [round(seed * ((1 + d) ** i), 4) for i in range(-5, 1)]  # synth 6-point history
    history = [to_float(x) for x in history]
    fit = _fit_trend(history)
    d = defaults["drift"] if drift is None else drift
    last = history[-1]
    base_vol = fit["vol"] or abs(last) * defaults["vol"]
    series = []
    for h in range(1, horizon + 1):
        point = _ensemble_point(fit, d, h, last)
        band = base_vol * (h ** 0.5) + abs(point) * defaults["vol"] * 0.2
        series.append({"t": h, "point": round(point, 4),
                       "lower": round(point - 1.96 * band, 4),
                       "upper": round(point + 1.96 * band, 4)})
    growth = cagr(history[0], series[-1]["point"], (len(history) + horizon) / 12.0) if history[0] else None
    metrics = {"history_points": len(history), "fitted_slope": round(fit["slope"], 4),
               "implied_cagr_pct": round(growth * 100, 2) if growth is not None else None,
               "terminal_value": series[-1]["point"],
               "terminal_range": [series[-1]["lower"], series[-1]["upper"]]}
    results = {"series": series, "metrics": metrics}
    g = grounding_block(f"{forecast_type.title()} Forecast", {"metrics": metrics, "history": history})
    row = FinForecast(
        tenant_id=tenant_id, subject_ref=subject_ref, assessment_id=assessment_id,
        forecast_type=forecast_type, method="ensemble", horizon=horizon, frequency=frequency,
        inputs={"history": history, "drift": d}, series=series, metrics=metrics,
        narrative=(f"{forecast_type.title()} projected to {series[-1]['point']:,.2f} over "
                   f"{horizon} {frequency} periods (95% CI)."),
        checksum=checksum(results), created_by=created_by)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"forecast_id": row.id, "forecast_type": forecast_type, "horizon": horizon,
            "series": series, "metrics": metrics, "narrative": row.narrative}


def multi_horizon(db: Session, *, forecast_type: str, subject_ref: Optional[str] = None,
                  assessment_id: Optional[int] = None, horizons: Optional[List[int]] = None,
                  history: Optional[List[float]] = None, tenant_id: Optional[int] = None,
                  created_by: Optional[str] = None) -> Dict[str, Any]:
    """Convenience: run the same forecast at several horizons (e.g. 3/6/12/24)."""
    horizons = horizons or [3, 6, 12, 24]
    out = {}
    for h in horizons:
        f = forecast(db, forecast_type=forecast_type, subject_ref=subject_ref,
                     assessment_id=assessment_id, horizon=h, history=history,
                     tenant_id=tenant_id, created_by=created_by)
        out[str(h)] = {"terminal_value": f["metrics"]["terminal_value"],
                       "terminal_range": f["metrics"]["terminal_range"],
                       "forecast_id": f["forecast_id"]}
    return {"forecast_type": forecast_type, "horizons": out}


def list_forecasts(db: Session, *, forecast_type: Optional[str] = None,
                   subject_ref: Optional[str] = None, limit: int = 50,
                   tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinForecast)
    if tenant_id is not None:
        q = q.filter(FinForecast.tenant_id == tenant_id)
    if forecast_type:
        q = q.filter(FinForecast.forecast_type == forecast_type)
    if subject_ref:
        q = q.filter(FinForecast.subject_ref == subject_ref)
    return [{"forecast_id": f.id, "forecast_type": f.forecast_type, "subject_ref": f.subject_ref,
             "horizon": f.horizon, "checksum": f.checksum, "created_at": iso(f.created_at)}
            for f in q.order_by(FinForecast.id.desc()).limit(limit).all()]


def get_forecast(db: Session, forecast_id: int) -> Optional[Dict[str, Any]]:
    f = db.query(FinForecast).filter(FinForecast.id == forecast_id).first()
    if not f:
        return None
    return {"forecast_id": f.id, "forecast_type": f.forecast_type, "subject_ref": f.subject_ref,
            "horizon": f.horizon, "frequency": f.frequency, "series": f.series,
            "metrics": f.metrics, "narrative": f.narrative, "created_at": iso(f.created_at)}
