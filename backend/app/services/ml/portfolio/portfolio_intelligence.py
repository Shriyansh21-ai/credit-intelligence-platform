"""Portfolio aggregation engine — pure, deterministic risk roll-ups.

Standard credit-portfolio mathematics:
* Exposure at Default (EAD) proxied by the recommended facility size.
* Expected Loss  EL  = Σ PDᵢ · LGDᵢ · EADᵢ
* Unexpected Loss UL  = √ Σ (EADᵢ · LGDᵢ)² · PDᵢ · (1 − PDᵢ)   (independence assumption)
* Concentration measured with the Herfindahl-Hirschman Index (HHI) on exposure
  shares.

All figures are derived, never fabricated: a portfolio with no positions returns
a well-defined empty result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Position:
    """One exposure in the portfolio (one enterprise assessment)."""

    client_id: int
    company_name: str
    industry: str
    region: str
    rating: str
    score: int
    pd: float
    lgd: float
    exposure: float

    @property
    def expected_loss(self) -> float:
        return self.pd * self.lgd * self.exposure

    @property
    def unexpected_loss(self) -> float:
        return self.exposure * self.lgd * math.sqrt(max(0.0, self.pd * (1.0 - self.pd)))


def position_from_assessment(record: Any) -> Position:
    """Map a persisted ``EnterpriseAssessment`` row to a portfolio position."""
    exposure = float(getattr(record, "recommended_loan_amount", 0.0) or 0.0)
    # Fall back to a nominal exposure so a zero-facility client still contributes
    # to counts and distributions without distorting loss figures.
    return Position(
        client_id=int(getattr(record, "id", 0) or 0),
        company_name=getattr(record, "company_name", "Unknown") or "Unknown",
        industry=(getattr(record, "industry", None) or "Unspecified"),
        region=(getattr(record, "country", None) or "Unspecified"),
        rating=(getattr(record, "risk_rating", None) or "NR"),
        score=int(getattr(record, "enterprise_credit_score", 0) or 0),
        pd=float(getattr(record, "probability_of_default", 0.0) or 0.0),
        lgd=float(getattr(record, "loss_given_default", 0.0) or 0.0),
        exposure=exposure,
    )


def _health_status(score: float) -> str:
    if score >= 760:
        return "Strong"
    if score >= 640:
        return "Satisfactory"
    if score >= 520:
        return "Watch"
    return "High Risk"


def _concentration_label(hhi: float) -> str:
    if hhi >= 0.25:
        return "concentrated"
    if hhi >= 0.15:
        return "moderate"
    return "diversified"


def _distribution(positions: List[Position], key: Callable[[Position], str],
                  total_exposure: float) -> List[dict]:
    groups: Dict[str, List[Position]] = {}
    for p in positions:
        groups.setdefault(key(p), []).append(p)

    rows = []
    for name, members in groups.items():
        exposure = sum(p.exposure for p in members)
        el = sum(p.expected_loss for p in members)
        rows.append({
            "key": name,
            "client_count": len(members),
            "exposure": round(exposure, 2),
            "exposure_share": round(exposure / total_exposure, 4) if total_exposure else 0.0,
            "expected_loss": round(el, 2),
            "average_pd": round(sum(p.pd for p in members) / len(members), 6),
        })
    rows.sort(key=lambda r: r["exposure"], reverse=True)
    return rows


def _hhi(rows: List[dict]) -> float:
    return round(sum(r["exposure_share"] ** 2 for r in rows), 4)


def _empty_result() -> dict:
    return {
        "summary": {
            "client_count": 0, "total_exposure": 0.0, "expected_loss": 0.0,
            "unexpected_loss": 0.0, "expected_loss_rate": 0.0,
            "portfolio_default_probability": 0.0, "weighted_average_score": 0,
            "portfolio_health": {"score": 0, "status": "No Exposure"},
        },
        "distributions": {"by_industry": [], "by_rating": [], "by_region": []},
        "concentration": {"industry_hhi": 0.0, "region_hhi": 0.0, "rating_hhi": 0.0,
                          "assessment": "diversified", "top_industry_share": 0.0},
        "top_risk_clients": [],
    }


def analyze(positions: List[Position], top_n: int = 10) -> dict:
    """Roll a list of positions up into portfolio-level intelligence."""
    if not positions:
        return _empty_result()

    total_exposure = sum(p.exposure for p in positions)
    total_el = sum(p.expected_loss for p in positions)
    total_ul = math.sqrt(sum(p.unexpected_loss ** 2 for p in positions))

    if total_exposure:
        weighted_pd = sum(p.pd * p.exposure for p in positions) / total_exposure
        weighted_score = sum(p.score * p.exposure for p in positions) / total_exposure
    else:
        weighted_pd = sum(p.pd for p in positions) / len(positions)
        weighted_score = sum(p.score for p in positions) / len(positions)

    by_industry = _distribution(positions, lambda p: p.industry, total_exposure)
    by_rating = _distribution(positions, lambda p: p.rating, total_exposure)
    by_region = _distribution(positions, lambda p: p.region, total_exposure)

    industry_hhi = _hhi(by_industry)

    top_clients = sorted(positions, key=lambda p: p.expected_loss, reverse=True)[:top_n]

    return {
        "summary": {
            "client_count": len(positions),
            "total_exposure": round(total_exposure, 2),
            "expected_loss": round(total_el, 2),
            "unexpected_loss": round(total_ul, 2),
            "expected_loss_rate": round(total_el / total_exposure, 6) if total_exposure else 0.0,
            "portfolio_default_probability": round(weighted_pd, 6),
            "weighted_average_score": int(round(weighted_score)),
            "portfolio_health": {
                "score": int(round(weighted_score)),
                "status": _health_status(weighted_score),
            },
        },
        "distributions": {
            "by_industry": by_industry,
            "by_rating": by_rating,
            "by_region": by_region,
        },
        "concentration": {
            "industry_hhi": industry_hhi,
            "region_hhi": _hhi(by_region),
            "rating_hhi": _hhi(by_rating),
            "top_industry_share": by_industry[0]["exposure_share"] if by_industry else 0.0,
            "assessment": _concentration_label(industry_hhi),
        },
        "top_risk_clients": [
            {
                "client_id": p.client_id,
                "company_name": p.company_name,
                "industry": p.industry,
                "region": p.region,
                "rating": p.rating,
                "score": p.score,
                "probability_of_default": round(p.pd, 6),
                "exposure": round(p.exposure, 2),
                "expected_loss": round(p.expected_loss, 2),
            }
            for p in top_clients
        ],
    }
