"""Portfolio ML.

Aggregates model-scored positions into portfolio-level risk analytics driven by
the trained model rather than a fixed formula

* portfolio default rate (exposure-weighted expected PD)
* expected loss and unexpected loss (independent-obligor approximation)
* sector concentration (Herfindahl–Hirschman Index over exposures)
* exposure risk (largest expected-loss contributors)
* rating-migration probability (grade distribution + downgrade likelihood)
* risk clustering of the book.

This complements — and never replaces — the deterministic portfolio
engine (:mod:`portfolio_intelligence`); both remain available.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Mapping, Optional

import numpy as np
from sqlalchemy.orm import Session

from backend.app.services.ml import serving

_DEFAULT_EAD = 1_000_000.0
_DEFAULT_LGD = 0.45
# PD bands → internal grade buckets for migration analysis.
_PD_BANDS = [(0.05, "very_low"), (0.10, "low"), (0.20, "moderate"),
             (0.35, "elevated"), (1.01, "high")]


def _band(pd: float) -> str:
    for cutoff, label in _PD_BANDS:
        if pd < cutoff:
            return label
    return "high"


def score_positions(
    db: Session,
    positions: List[Mapping[str, Any]],
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Score each position through the resolved model (no logging noise)."""
    scored: List[Dict[str, Any]] = []
    for pos in positions:
        mapping = pos if isinstance(pos, Mapping) else {}
        features = mapping.get("features", pos) if isinstance(pos, Mapping) else pos
        res = serving.predict(db, features, model_id=model_id, model_key=model_key,
                              inference_type="portfolio", log=False, use_cache=True)
        pred = res.get("prediction") or {}
        pd = pred.get("probability_of_default")
        # ``.get`` with a default does not help when the key is present-but-None
        # (e.g. a serialised Pydantic model), so coalesce explicitly.
        exposure = mapping.get("exposure")
        lgd = mapping.get("lgd")
        scored.append({
            "entity_id": mapping.get("entity_id"),
            "sector": mapping.get("sector") or "unclassified",
            "exposure": float(exposure) if exposure is not None else _DEFAULT_EAD,
            "lgd": float(lgd) if lgd is not None else _DEFAULT_LGD,
            "pd": pd,
            "risk_grade": pred.get("risk_grade"),
            "risk_band": _band(pd) if pd is not None else None,
        })
    return scored


def portfolio_metrics(scored: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate scored positions into portfolio risk analytics."""
    valid = [s for s in scored if s.get("pd") is not None]
    if not valid:
        return {"positions": 0}

    pds = np.array([s["pd"] for s in valid], dtype=float)
    ead = np.array([s["exposure"] for s in valid], dtype=float)
    lgd = np.array([s["lgd"] for s in valid], dtype=float)
    total_exposure = float(ead.sum())

    el_contrib = pds * ead * lgd
    expected_loss = float(el_contrib.sum())
    # Independent-obligor unexpected loss (portfolio std of loss).
    ul = float(np.sqrt(np.sum((ead * lgd) ** 2 * pds * (1 - pds))))

    # Sector concentration (HHI over exposure shares).
    sector_exposure: Dict[str, float] = {}
    for s in valid:
        sector_exposure[s["sector"]] = sector_exposure.get(s["sector"], 0.0) + s["exposure"]
    shares = np.array(list(sector_exposure.values())) / total_exposure if total_exposure else np.array([])
    hhi = float(np.sum(shares ** 2)) if shares.size else 0.0

    band_dist = Counter(s["risk_band"] for s in valid)
    grade_dist = Counter(s["risk_grade"] for s in valid if s["risk_grade"])
    downgrade_prone = sum(1 for s in valid if s["risk_band"] in ("elevated", "high"))

    # Top exposures by expected-loss contribution.
    ranked = sorted(zip(valid, el_contrib.tolist()), key=lambda kv: kv[1], reverse=True)[:10]
    top_exposures = [
        {"entity_id": s["entity_id"], "sector": s["sector"], "pd": round(s["pd"], 6),
         "exposure": s["exposure"], "expected_loss": round(elc, 2)}
        for s, elc in ranked
    ]

    return {
        "positions": len(valid),
        "total_exposure": round(total_exposure, 2),
        "portfolio_default_rate": round(float(np.average(pds, weights=ead)), 6),
        "average_pd": round(float(pds.mean()), 6),
        "expected_loss": round(expected_loss, 2),
        "expected_loss_rate": round(expected_loss / total_exposure, 6) if total_exposure else None,
        "unexpected_loss": round(ul, 2),
        "sector_concentration_hhi": round(hhi, 6),
        "sector_concentration_band": _hhi_band(hhi),
        "sector_exposure": {k: round(v, 2) for k, v in sector_exposure.items()},
        "risk_band_distribution": dict(band_dist),
        "grade_distribution": dict(grade_dist),
        "migration": {
            "downgrade_prone_positions": downgrade_prone,
            "downgrade_prone_share": round(downgrade_prone / len(valid), 6),
        },
        "top_exposures": top_exposures,
    }


def _hhi_band(hhi: float) -> str:
    if hhi >= 0.25:
        return "highly_concentrated"
    if hhi >= 0.15:
        return "moderately_concentrated"
    return "diversified"


def risk_clusters(scored: List[Dict[str, Any]], n_clusters: int = 3) -> List[Dict[str, Any]]:
    """Cluster the book by (PD, exposure) into risk tiers."""
    valid = [s for s in scored if s.get("pd") is not None]
    if len(valid) < n_clusters:
        return []
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    X = np.array([[s["pd"], s["exposure"]] for s in valid], dtype=float)
    Xs = StandardScaler().fit_transform(X)
    labels = KMeans(n_clusters=n_clusters, random_state=5, n_init=10).fit_predict(Xs)
    clusters: List[Dict[str, Any]] = []
    for c in sorted(set(labels.tolist())):
        mask = labels == c
        clusters.append({
            "cluster": int(c),
            "size": int(mask.sum()),
            "avg_pd": round(float(X[mask, 0].mean()), 6),
            "avg_exposure": round(float(X[mask, 1].mean()), 2),
        })
    return sorted(clusters, key=lambda x: x["avg_pd"], reverse=True)


def analyze(
    db: Session,
    positions: List[Mapping[str, Any]],
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    with_clusters: bool = True,
) -> Dict[str, Any]:
    """Score positions and return full portfolio ML analytics."""
    scored = score_positions(db, positions, model_id=model_id, model_key=model_key)
    result = {"metrics": portfolio_metrics(scored)}
    if with_clusters:
        result["risk_clusters"] = risk_clusters(scored)
    return result


def analyze_current(
    db: Session,
    *,
    model_id: Optional[int] = None,
    model_key: Optional[str] = None,
    limit: int = 300,
) -> Dict[str, Any]:
    """Analyse the current portfolio from persisted feature vectors."""
    from backend.app.models.feature_vector import FeatureVector
    from backend.app.services.ml.inference import features_to_mapping

    vectors = (
        db.query(FeatureVector)
        .filter(FeatureVector.is_current.is_(True))
        .order_by(FeatureVector.created_at.desc())
        .limit(limit)
        .all()
    )
    positions = [
        {"entity_id": v.assessment_id,
         "features": features_to_mapping({"features": v.features or []})}
        for v in vectors
    ]
    return analyze(db, positions, model_id=model_id, model_key=model_key)
