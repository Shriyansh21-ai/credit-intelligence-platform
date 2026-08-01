"""M5 — AI evaluation framework.

Produces deterministic, reproducible **AI scorecards** across the dimensions a
bank's model-risk team cares about

    factual_accuracy · hallucination · groundedness · consistency ·
    policy_compliance · reasoning · latency · cost · token_usage · business_correctness

Every metric is computed from observable evidence (the generated text, the
grounding it was supposed to use, optional expected answers and the recorded LLM
usage) — no metric requires a network call, so evaluations are reproducible and
run offline. Results persist to ``aip_evaluations`` and roll up into a graded
scorecard; a suite runner (``aip_eval_cases``) supports regression testing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.ai_platform import (
    AIPAgentRun, AIPEvalCase, AIPEvaluation, AIPRagQuery, AIPReport,
)
from backend.app.services.ai_platform import common

_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*%?")

# Metric weights for the overall score.
_WEIGHTS = {
    "factual_accuracy": 0.18, "groundedness": 0.18, "hallucination": 0.15,
    "consistency": 0.10, "policy_compliance": 0.12, "reasoning": 0.08,
    "latency": 0.05, "cost": 0.04, "token_usage": 0.03, "business_correctness": 0.07,
}


def _grade(score: float) -> str:
    if score >= 0.9:
        return "A"
    if score >= 0.8:
        return "B"
    if score >= 0.7:
        return "C"
    if score >= 0.6:
        return "D"
    return "F"


# ---------------------------------------------------------------------------
# Individual metric computations (all deterministic)
# ---------------------------------------------------------------------------
def groundedness(output_text: str, grounding_text: str) -> float:
    sents = common.split_sentences(output_text)
    if not sents:
        return 0.0
    if not grounding_text:
        return 0.0
    g_tokens = set(common.keywords(grounding_text))
    grounded = 0
    for s in sents:
        st = set(common.keywords(s))
        if st and common.jaccard(st, g_tokens) > 0.12:
            grounded += 1
    return grounded / len(sents)


def hallucination(output_text: str, grounding_text: str) -> float:
    """Fraction of numeric claims in the output NOT supported by the grounding."""
    nums = [n.strip().replace(",", "") for n in _NUM_RE.findall(output_text or "")]
    nums = [n for n in nums if n not in ("", "-", ".")]
    if not nums:
        # No numeric claims → hallucination risk assessed lexically.
        gr = groundedness(output_text, grounding_text)
        return common.clamp(1.0 - gr)
    g = (grounding_text or "").replace(",", "")
    unsupported = sum(1 for n in nums if n not in g)
    return unsupported / len(nums)


def consistency(samples: List[str]) -> float:
    """Self-consistency: mean pairwise lexical similarity across samples."""
    samples = [s for s in samples if s]
    if len(samples) < 2:
        return 1.0
    sims, n = 0.0, 0
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            sims += common.jaccard(common.keywords(samples[i]), common.keywords(samples[j]))
            n += 1
    return sims / n if n else 1.0


def policy_compliance(output_text: str, citations: Optional[List[Any]],
                      require_citations: bool = True) -> float:
    text = (output_text or "").lower()
    score = 1.0
    # Fabrication-risk phrases penalised.
    for bad in ("i think", "probably", "as an ai", "i guess", "made up"):
        if bad in text:
            score -= 0.2
    if require_citations and not citations:
        score -= 0.3
    return common.clamp(score)


def reasoning_quality(output_text: str) -> float:
    sents = common.split_sentences(output_text)
    if not sents:
        return 0.0
    connectives = ("because", "therefore", "however", "since", "thus", "given",
                   "as a result", "consequently", "due to")
    has_conn = any(c in (output_text or "").lower() for c in connectives)
    structure = min(1.0, len(sents) / 4.0)
    return common.clamp(0.4 + 0.3 * structure + (0.3 if has_conn else 0.0))


def factual_accuracy(output_text: str, expected: Optional[str],
                     grounding_text: str) -> float:
    if expected:
        return common.clamp(common.jaccard(common.keywords(output_text),
                                           common.keywords(expected)) * 1.5)
    return groundedness(output_text, grounding_text)


def _latency_score(usage: Dict[str, Any]) -> float:
    ms = usage.get("latency_ms")
    if ms is None:
        return 1.0
    return common.clamp(1.0 - max(0.0, (ms - 500.0)) / 5000.0)


def _cost_score(usage: Dict[str, Any]) -> float:
    cost = usage.get("cost_usd")
    if cost is None:
        return 1.0
    return common.clamp(1.0 - cost / 0.10)


def _token_score(usage: Dict[str, Any]) -> float:
    tok = usage.get("total_tokens")
    if tok is None:
        return 1.0
    return common.clamp(1.0 - max(0, tok - 500) / 4000.0)


def business_correctness(output_text: str, expected_decision: Optional[str]) -> float:
    if not expected_decision:
        return 1.0
    return 1.0 if expected_decision.lower() in (output_text or "").lower() else 0.0


# ---------------------------------------------------------------------------
# Scorecard
# ---------------------------------------------------------------------------
def score_output(*, output_text: str, grounding_text: str = "",
                 citations: Optional[List[Any]] = None,
                 expected: Optional[str] = None,
                 expected_decision: Optional[str] = None,
                 samples: Optional[List[str]] = None,
                 usage: Optional[Dict[str, Any]] = None,
                 require_citations: bool = True) -> Dict[str, Any]:
    usage = usage or {}
    hall = hallucination(output_text, grounding_text)
    scores = {
        "factual_accuracy": factual_accuracy(output_text, expected, grounding_text),
        "groundedness": groundedness(output_text, grounding_text),
        "hallucination": 1.0 - hall,  # higher = better (fewer hallucinations)
        "consistency": consistency(samples or [output_text]),
        "policy_compliance": policy_compliance(output_text, citations, require_citations),
        "reasoning": reasoning_quality(output_text),
        "latency": _latency_score(usage),
        "cost": _cost_score(usage),
        "token_usage": _token_score(usage),
        "business_correctness": business_correctness(output_text, expected_decision),
    }
    overall = sum(scores[k] * w for k, w in _WEIGHTS.items())
    metrics = {
        "hallucination_rate": common.round_opt(hall, 4),
        "latency_ms": usage.get("latency_ms"),
        "cost_usd": usage.get("cost_usd"),
        "total_tokens": usage.get("total_tokens"),
    }
    scores = {k: common.round_opt(v, 4) for k, v in scores.items()}
    return {"scores": scores, "metrics": metrics,
            "overall_score": common.round_opt(overall, 4),
            "grade": _grade(overall), "passed": overall >= 0.7}


# ---------------------------------------------------------------------------
# Persisted evaluation
# ---------------------------------------------------------------------------
def evaluate(db: Session, *, target_type: str, output_text: str,
             grounding_text: str = "", citations: Optional[List[Any]] = None,
             expected: Optional[str] = None, expected_decision: Optional[str] = None,
             samples: Optional[List[str]] = None, usage: Optional[Dict[str, Any]] = None,
             target_ref: Optional[str] = None, suite: str = "default",
             require_citations: bool = True, tenant_id: Optional[int] = None,
             created_by: Optional[str] = None, persist: bool = True) -> Dict[str, Any]:
    card = score_output(output_text=output_text, grounding_text=grounding_text,
                        citations=citations, expected=expected,
                        expected_decision=expected_decision, samples=samples,
                        usage=usage, require_citations=require_citations)
    if persist:
        row = AIPEvaluation(
            tenant_id=tenant_id, target_type=target_type, target_ref=target_ref,
            suite=suite, metrics=card["metrics"], scores=card["scores"],
            overall_score=card["overall_score"], passed=card["passed"],
            provider=(usage or {}).get("provider"),
            meta={"grade": card["grade"]}, created_by=created_by,
            created_at=common.utcnow())
        db.add(row)
        db.commit()
        db.refresh(row)
        card["evaluation_id"] = row.id
    card["target_type"] = target_type
    card["target_ref"] = target_ref
    return card


# ---------------------------------------------------------------------------
# Convenience: evaluate persisted RAG / agent / report artifacts
# ---------------------------------------------------------------------------
def evaluate_rag_query(db: Session, *, query_id: int,
                       tenant_id: Optional[int] = None) -> Dict[str, Any]:
    q = db.query(AIPRagQuery).filter(AIPRagQuery.id == query_id).first()
    if q is None:
        raise ValueError("rag query not found")
    grounding_text = " ".join((c.get("snippet") or "") for c in (q.citations or []))
    return evaluate(db, target_type="rag", output_text=q.answer or "",
                    grounding_text=grounding_text, citations=q.citations,
                    target_ref=str(q.id),
                    usage={"latency_ms": q.latency_ms, "total_tokens": q.total_tokens,
                           "provider": q.provider}, tenant_id=tenant_id)


def evaluate_agent_run(db: Session, *, run_id: int,
                       tenant_id: Optional[int] = None) -> Dict[str, Any]:
    r = db.query(AIPAgentRun).filter(AIPAgentRun.id == run_id).first()
    if r is None:
        raise ValueError("agent run not found")
    result = r.result or {}
    text = result.get("executive_summary", "")
    grounding_text = " ".join(
        common.truncate(c.get("recommendation", ""), 200)
        for c in result.get("contributions", []))
    return evaluate(db, target_type="agent_run", output_text=text,
                    grounding_text=grounding_text,
                    citations=[c for c in result.get("contributions", []) if c.get("citations")],
                    expected_decision=result.get("decision"), target_ref=str(r.id),
                    require_citations=False, tenant_id=tenant_id)


def evaluate_report(db: Session, *, report_id: int,
                    tenant_id: Optional[int] = None) -> Dict[str, Any]:
    rep = db.query(AIPReport).filter(AIPReport.id == report_id).first()
    if rep is None:
        raise ValueError("report not found")
    body = " ".join(s.get("body", "") for s in (rep.sections or []) if isinstance(s, dict))
    grounding_text = " ".join(str(e.get("value", e)) for e in (rep.evidence or []))
    return evaluate(db, target_type="report", output_text=body,
                    grounding_text=grounding_text, citations=rep.citations,
                    target_ref=str(rep.id), require_citations=False, tenant_id=tenant_id)


# ---------------------------------------------------------------------------
# Eval suites (regression cases)
# ---------------------------------------------------------------------------
def add_case(db: Session, *, suite: str, name: str, input: Dict[str, Any],
             expected: Dict[str, Any], tenant_id: Optional[int] = None) -> AIPEvalCase:
    row = AIPEvalCase(tenant_id=tenant_id, suite=suite, name=name, input=input,
                      expected=expected, created_at=common.utcnow())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_evaluations(db: Session, *, tenant_id: Optional[int] = None,
                     target_type: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    q = db.query(AIPEvaluation).filter(AIPEvaluation.tenant_id == tenant_id)
    if target_type:
        q = q.filter(AIPEvaluation.target_type == target_type)
    return [{"id": e.id, "target_type": e.target_type, "target_ref": e.target_ref,
             "overall_score": e.overall_score, "grade": (e.meta or {}).get("grade"),
             "passed": e.passed, "scores": e.scores, "created_at": common.iso(e.created_at)}
            for e in q.order_by(AIPEvaluation.id.desc()).limit(limit).all()]


def summary(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    rows = db.query(AIPEvaluation).filter(AIPEvaluation.tenant_id == tenant_id).all()
    if not rows:
        return {"count": 0, "mean_overall": None, "pass_rate": None, "by_type": {}}
    by_type: Dict[str, List[float]] = {}
    for r in rows:
        by_type.setdefault(r.target_type, []).append(r.overall_score or 0.0)
    return {
        "count": len(rows),
        "mean_overall": common.round_opt(sum((r.overall_score or 0) for r in rows) / len(rows), 4),
        "pass_rate": common.round_opt(sum(1 for r in rows if r.passed) / len(rows), 4),
        "by_type": {k: common.round_opt(sum(v) / len(v), 4) for k, v in by_type.items()},
    }
