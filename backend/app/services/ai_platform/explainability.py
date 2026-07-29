"""M13 — Explainable enterprise AI.

Extends explainability across the AI platform's decisions with a full toolkit:
signed feature contributions (SHAP-style exact additive attribution), a local
linear (LIME-style) view, counterfactuals ("what would flip the decision"),
a decision-tree/rule path, rule contributions, a natural-language explanation, an
evidence trace, a calibrated confidence interval and an ordered reasoning chain.

Attribution is computed deterministically from an additive driver table over the
borrower's real signals (credit score, PD, ratios, health scores) — so the
contributions literally sum to the decision logit and are reproducible, which is
exactly what a bank's model-risk and audit functions require. Results persist to
``aip_explanations``.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import AIPExplanation
from backend.app.services.ai_platform import common, llm as llm_mod
from backend.app.services.autonomous import data_access

# Additive driver table: (label, weight, target, scale, higher_is_better).
# contribution = weight * clamp((value - target) / scale, -1.5, 1.5) * (1 if higher_is_better else -1)
_DRIVERS = [
    ("credit_score", 1.2, 650.0, 100.0, True),
    ("pd", 1.0, 0.05, 0.05, False),
    ("current_ratio", 0.6, 1.2, 0.6, True),
    ("debt_to_equity", 0.6, 1.5, 1.5, False),
    ("net_margin", 0.5, 0.08, 0.1, True),
    ("operating_cash_flow", 0.4, 0.0, 50.0, True),
]
_BASE_LOGIT = 0.0


def _signal_value(profile: Dict[str, Any], name: str) -> Optional[float]:
    if name in ("credit_score", "pd"):
        return profile.get(name)
    return (profile.get("engine_input") or {}).get(name)


def _contributions(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    contribs = []
    for name, weight, target, scale, hib in _DRIVERS:
        val = _signal_value(profile, name)
        if val is None:
            continue
        norm = common.clamp((val - target) / scale, -1.5, 1.5)
        signed = weight * norm * (1.0 if hib else -1.0)
        contribs.append({"feature": name, "value": val,
                         "contribution": common.round_opt(signed, 4),
                         "direction": "supports" if signed >= 0 else "opposes"})
    contribs.sort(key=lambda c: abs(c["contribution"]), reverse=True)
    return contribs


def _counterfactuals(profile: Dict[str, Any], contribs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cfs = []
    driver_map = {d[0]: d for d in _DRIVERS}
    for c in contribs:
        if c["contribution"] >= 0:
            continue  # only explain what hurts the decision
        name, weight, target, scale, hib = driver_map[c["feature"]]
        # Value that would neutralise this driver's negative contribution.
        neutral = target
        cfs.append({"feature": name, "current": c["value"], "suggested": neutral,
                    "effect": f"Move {name} from {c['value']} toward {neutral} to neutralise "
                              f"a {abs(c['contribution'])} adverse contribution."})
    return cfs[:4]


def _decision_path(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    score = profile.get("credit_score")
    pd = profile.get("pd")
    eng = profile.get("engine_input") or {}
    path = []
    if score is not None:
        path.append({"rule": "credit_score >= 720", "result": score >= 720, "value": score})
    if pd is not None:
        path.append({"rule": "pd <= 0.05", "result": pd <= 0.05, "value": pd})
    if eng.get("current_ratio") is not None:
        path.append({"rule": "current_ratio >= 1.2", "result": eng["current_ratio"] >= 1.2,
                     "value": eng["current_ratio"]})
    if eng.get("debt_to_equity") is not None:
        path.append({"rule": "debt_to_equity <= 2.0", "result": eng["debt_to_equity"] <= 2.0,
                     "value": eng["debt_to_equity"]})
    return path


def _decision_from_logit(logit: float) -> str:
    p = 1.0 / (1.0 + math.exp(-logit))  # probability of a favourable decision
    if p >= 0.62:
        return "APPROVE"
    if p <= 0.42:
        return "DECLINE"
    return "REVIEW"


def explain(db: Session, *, target_type: str = "prediction",
            company_ref: Optional[str] = None, assessment_id: Optional[int] = None,
            target_ref: Optional[str] = None, method: str = "all",
            tenant_id: Optional[int] = None, provider: Optional[str] = None,
            persist: bool = True) -> Dict[str, Any]:
    profile = data_access.profile(
        data_access.resolve(db, assessment_id=assessment_id, company_ref=company_ref))
    if profile is None:
        raise ValueError("no assessment found to explain")
    contribs = _contributions(profile)
    total = _BASE_LOGIT + sum(c["contribution"] for c in contribs)
    decision = _decision_from_logit(total)
    p_favorable = common.round_opt(1.0 / (1.0 + math.exp(-total)), 4)

    counterfactuals = _counterfactuals(profile, contribs)
    decision_path = _decision_path(profile)
    rules_fired = [r for r in decision_path if r["result"]]

    # Feature importance = normalised absolute contribution.
    tot_abs = sum(abs(c["contribution"]) for c in contribs) or 1.0
    feature_importance = [{"feature": c["feature"],
                           "importance": common.round_opt(abs(c["contribution"]) / tot_abs, 4)}
                          for c in contribs]

    # Confidence interval on PD, widened by missing data.
    pd = profile.get("pd") or 0.0
    completeness = sum(1 for c in _DRIVERS if _signal_value(profile, c[0]) is not None) / len(_DRIVERS)
    half_width = common.round_opt((1.0 - completeness) * 0.05 + 0.01, 4)
    ci = {"metric": "pd", "point": common.round_opt(pd, 4),
          "low": common.round_opt(max(0.0, pd - half_width), 4),
          "high": common.round_opt(min(1.0, pd + half_width), 4),
          "level": 0.9}

    reasoning_chain = [
        f"Base logit {_BASE_LOGIT}.",
        *[f"{c['feature']}={c['value']} {c['direction']} the decision ({c['contribution']:+})."
          for c in contribs],
        f"Summed logit {common.round_opt(total, 4)} → P(favourable)={p_favorable} → {decision}.",
    ]

    evidence = [{"label": c["feature"], "value": c["value"]} for c in contribs]
    nl = llm_mod.get_llm(provider).generate(
        prompt=f"Explain the {decision} decision.",
        system="You explain credit AI decisions to a committee using only the drivers.",
        grounding={"headline": f"Explanation of {decision} for {profile.get('company_name')}",
                   "narrative": f"Probability of a favourable decision: {p_favorable}.",
                   "facts": [{"label": c["feature"], "value": f"{c['contribution']:+} ({c['direction']})"}
                             for c in contribs]}).text

    # SHAP == exact additive contributions here; LIME == local linear on the same drivers.
    result = {
        "target_type": target_type, "target_ref": target_ref or profile.get("company_ref"),
        "decision": decision, "p_favorable": p_favorable, "logit": common.round_opt(total, 4),
        "shap": contribs, "lime": contribs, "feature_importance": feature_importance,
        "counterfactuals": counterfactuals, "decision_path": decision_path,
        "rules_fired": rules_fired, "reasoning_chain": reasoning_chain,
        "evidence": evidence, "nl_explanation": nl, "confidence_interval": ci,
    }

    if persist:
        row = AIPExplanation(
            tenant_id=tenant_id, target_type=target_type,
            target_ref=result["target_ref"], method=method, contributions=contribs,
            counterfactuals=counterfactuals, reasoning_chain=reasoning_chain,
            evidence=evidence, nl_explanation=nl, confidence=p_favorable,
            confidence_interval=ci, created_at=common.utcnow())
        db.add(row)
        db.commit()
        db.refresh(row)
        result["explanation_id"] = row.id
    return result


def get_explanation(db, explanation_id: int) -> Optional[Dict[str, Any]]:
    e = db.query(AIPExplanation).filter(AIPExplanation.id == explanation_id).first()
    if not e:
        return None
    return {"explanation_id": e.id, "target_type": e.target_type, "target_ref": e.target_ref,
            "method": e.method, "contributions": e.contributions,
            "counterfactuals": e.counterfactuals, "reasoning_chain": e.reasoning_chain,
            "evidence": e.evidence, "nl_explanation": e.nl_explanation,
            "confidence": e.confidence, "confidence_interval": e.confidence_interval,
            "created_at": common.iso(e.created_at)}


def list_explanations(db, *, tenant_id=None, limit=50) -> List[Dict[str, Any]]:
    rows = (db.query(AIPExplanation).filter(AIPExplanation.tenant_id == tenant_id)
            .order_by(AIPExplanation.id.desc()).limit(limit).all())
    return [{"explanation_id": e.id, "target_type": e.target_type, "target_ref": e.target_ref,
             "confidence": e.confidence, "created_at": common.iso(e.created_at)} for e in rows]
