"""Bank statement analytics engine (Milestone 5).

Turns raw imported transactions into lending-grade signals:

* **Cash flow** — monthly inflow/outflow/net and totals.
* **Salary detection** / **vendor payments** / **collections** — categorised flows.
* **Cheque bounce detection** — count + inferred severity.
* **Balance analytics** — average / monthly / min / max balance and a daily series.
* **Liquidity trend** — direction of the monthly closing-balance series.
* **Working capital cycle** — inflow-vs-outflow timing proxy (days).
* **Seasonality** — coefficient of variation of monthly inflows.
* **Cash burn** — average net burn in loss-making months + runway.
* **Bank health score** — a 0–100 composite over the signals above.

The core :func:`compute_metrics` is a pure function over transaction dicts so it
is trivially testable; :func:`analyze_statement` / :func:`analyze_entity` add DB
loading + persistence.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.integrations import (
    BankStatement,
    BankTransaction,
    StatementAnalytics,
)


def _month_key(dt: Any) -> str:
    if isinstance(dt, str):
        return dt[:7]
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m")
    return "unknown"


def _trend(values: List[float]) -> str:
    if len(values) < 2:
        return "flat"
    first = mean(values[: max(1, len(values) // 2)])
    second = mean(values[len(values) // 2:])
    if second > first * 1.05:
        return "improving"
    if second < first * 0.95:
        return "deteriorating"
    return "flat"


def compute_metrics(
    transactions: List[Dict[str, Any]],
    *,
    opening_balance: float = 0.0,
    closing_balance: Optional[float] = None,
) -> Dict[str, Any]:
    """Compute the full analytics suite from a list of transaction dicts."""
    if not transactions:
        return {
            "transaction_count": 0,
            "bank_health_score": 0.0,
            "note": "no transactions",
        }

    # Normalise + sort.
    txns = sorted(transactions, key=lambda t: str(t.get("txn_date", "")))
    monthly = defaultdict(lambda: {"inflow": 0.0, "outflow": 0.0, "closing": None})
    by_category = defaultdict(lambda: {"count": 0, "amount": 0.0})
    balances: List[float] = []
    daily_balance: Dict[str, float] = {}
    bounce_count = 0

    for t in txns:
        amt = float(t.get("amount", 0.0) or 0.0)
        direction = t.get("direction", "debit")
        mk = _month_key(t.get("txn_date"))
        cat = t.get("category") or "uncategorized"
        by_category[cat]["count"] += 1
        by_category[cat]["amount"] += amt
        if cat == "cheque_bounce":
            bounce_count += 1
        if direction == "credit":
            monthly[mk]["inflow"] += amt
        else:
            monthly[mk]["outflow"] += amt
        bal = t.get("balance")
        if bal is not None:
            balances.append(float(bal))
            monthly[mk]["closing"] = float(bal)
            daily_balance[str(t.get("txn_date"))[:10]] = float(bal)

    months = sorted(monthly.keys())
    monthly_rows = []
    for mk in months:
        m = monthly[mk]
        monthly_rows.append({
            "month": mk,
            "inflow": round(m["inflow"], 2),
            "outflow": round(m["outflow"], 2),
            "net": round(m["inflow"] - m["outflow"], 2),
            "closing_balance": round(m["closing"], 2) if m["closing"] is not None else None,
        })

    total_inflow = sum(r["inflow"] for r in monthly_rows)
    total_outflow = sum(r["outflow"] for r in monthly_rows)
    net_cash_flow = round(total_inflow - total_outflow, 2)

    inflows = [r["inflow"] for r in monthly_rows]
    monthly_closings = [r["closing_balance"] for r in monthly_rows if r["closing_balance"] is not None]

    # Salary / vendor / collections.
    salary = by_category.get("salary", {"count": 0, "amount": 0.0})
    vendor = by_category.get("vendor", {"count": 0, "amount": 0.0})
    collections = by_category.get("collection", {"count": 0, "amount": 0.0})

    # Balance analytics.
    avg_balance = round(mean(balances), 2) if balances else 0.0
    min_balance = round(min(balances), 2) if balances else 0.0
    max_balance = round(max(balances), 2) if balances else 0.0

    # Liquidity trend.
    liquidity_trend = _trend(monthly_closings) if monthly_closings else "flat"

    # Seasonality — coefficient of variation of monthly inflow.
    seasonality = 0.0
    if len(inflows) >= 2 and mean(inflows) > 0:
        seasonality = round(pstdev(inflows) / mean(inflows), 4)

    # Working-capital-cycle proxy (days) — how long the balance sustains outflow.
    avg_monthly_outflow = (total_outflow / len(monthly_rows)) if monthly_rows else 0.0
    wc_cycle_days = round((avg_balance / avg_monthly_outflow) * 30, 1) if avg_monthly_outflow else 0.0

    # Cash burn — average net in loss-making months + runway.
    burn_months = [r["net"] for r in monthly_rows if r["net"] < 0]
    avg_burn = round(abs(mean(burn_months)), 2) if burn_months else 0.0
    last_balance = closing_balance if closing_balance is not None else (
        monthly_closings[-1] if monthly_closings else 0.0)
    runway_months = round(last_balance / avg_burn, 1) if avg_burn > 0 else None

    # Bank health score (0-100).
    score = _health_score(
        net_cash_flow=net_cash_flow,
        total_inflow=total_inflow,
        bounce_count=bounce_count,
        n_months=len(monthly_rows),
        seasonality=seasonality,
        min_balance=min_balance,
        avg_balance=avg_balance,
        avg_monthly_outflow=avg_monthly_outflow,
        liquidity_trend=liquidity_trend,
    )

    return {
        "transaction_count": len(txns),
        "period_months": len(monthly_rows),
        "cash_flow": {
            "total_inflow": round(total_inflow, 2),
            "total_outflow": round(total_outflow, 2),
            "net_cash_flow": net_cash_flow,
            "monthly": monthly_rows,
        },
        "salary_detection": {
            "detected": salary["count"] > 0,
            "payouts": salary["count"],
            "total_paid": round(salary["amount"], 2),
        },
        "vendor_payments": {"count": vendor["count"], "total": round(vendor["amount"], 2)},
        "collections": {"count": collections["count"], "total": round(collections["amount"], 2)},
        "cheque_bounce": {
            "count": bounce_count,
            "severity": "high" if bounce_count >= 3 else ("medium" if bounce_count >= 1 else "none"),
        },
        "average_balance": avg_balance,
        "min_balance": min_balance,
        "max_balance": max_balance,
        "monthly_balance": [{"month": r["month"], "closing_balance": r["closing_balance"]} for r in monthly_rows],
        "daily_balance": [{"date": d, "balance": round(b, 2)} for d, b in sorted(daily_balance.items())],
        "liquidity_trend": liquidity_trend,
        "working_capital_cycle_days": wc_cycle_days,
        "seasonality_index": seasonality,
        "cash_burn": {"avg_monthly_burn": avg_burn, "runway_months": runway_months,
                      "burn_months": len(burn_months)},
        "bank_health_score": score,
    }


def _health_score(
    *, net_cash_flow: float, total_inflow: float, bounce_count: int, n_months: int,
    seasonality: float, min_balance: float, avg_balance: float,
    avg_monthly_outflow: float, liquidity_trend: str,
) -> float:
    """Composite 0-100 bank-health score."""
    score = 50.0
    # Positive cumulative cash flow relative to inflow.
    if total_inflow > 0:
        ratio = net_cash_flow / total_inflow
        score += max(-25, min(25, ratio * 100))
    # Cheque bounces are strongly negative.
    score -= min(25, bounce_count * (25 / max(1, n_months)) * 3)
    # Liquidity trend.
    score += {"improving": 10, "flat": 0, "deteriorating": -12}.get(liquidity_trend, 0)
    # Balance cushion vs monthly outflow.
    if avg_monthly_outflow > 0:
        cushion = avg_balance / avg_monthly_outflow
        score += max(-10, min(15, (cushion - 1) * 10))
    # Never negative min balance overdraws too far.
    if min_balance < 0:
        score -= 10
    # High seasonality (volatility) is a mild negative.
    score -= min(10, seasonality * 10)
    return round(max(0.0, min(100.0, score)), 1)


# ---------------------------------------------------------------------------
# DB-backed entry points
# ---------------------------------------------------------------------------
def analyze_statement(db: Session, statement_id: int, *, persist: bool = True) -> Dict[str, Any]:
    stmt = db.query(BankStatement).get(statement_id)
    if stmt is None:
        raise ValueError("statement not found")
    rows = db.query(BankTransaction).filter(BankTransaction.statement_id == statement_id).all()
    txns = [{
        "txn_date": r.txn_date, "amount": r.amount, "direction": r.direction,
        "balance": r.balance, "category": r.category, "counterparty": r.counterparty,
        "mode": r.mode, "is_recurring": r.is_recurring,
    } for r in rows]
    metrics = compute_metrics(txns, opening_balance=stmt.opening_balance or 0.0,
                              closing_balance=stmt.closing_balance)
    if persist:
        _persist(db, entity_ref=stmt.entity_ref, application_id=stmt.application_id,
                 statement_id=stmt.id, scope="statement", metrics=metrics)
    return metrics


def analyze_entity(db: Session, entity_ref: str, *, persist: bool = True) -> Dict[str, Any]:
    """Analyse all statements for an entity together (whole-entity view)."""
    stmts = db.query(BankStatement).filter(BankStatement.entity_ref == entity_ref).all()
    if not stmts:
        raise ValueError("no statements for entity")
    stmt_ids = [s.id for s in stmts]
    rows = db.query(BankTransaction).filter(BankTransaction.statement_id.in_(stmt_ids)).all()
    txns = [{
        "txn_date": r.txn_date, "amount": r.amount, "direction": r.direction,
        "balance": r.balance, "category": r.category, "is_recurring": r.is_recurring,
    } for r in rows]
    closing = max((s.closing_balance or 0.0) for s in stmts)
    metrics = compute_metrics(txns, closing_balance=closing)
    if persist:
        _persist(db, entity_ref=entity_ref, application_id=stmts[0].application_id,
                 statement_id=None, scope="entity", metrics=metrics)
    return metrics


def _persist(db: Session, *, entity_ref: str, application_id: Optional[int],
             statement_id: Optional[int], scope: str, metrics: Dict[str, Any]) -> StatementAnalytics:
    prev = (db.query(StatementAnalytics)
            .filter(StatementAnalytics.entity_ref == entity_ref,
                    StatementAnalytics.scope == scope,
                    StatementAnalytics.statement_id == statement_id)
            .order_by(StatementAnalytics.version.desc()).first())
    version = (prev.version + 1) if prev else 1
    row = StatementAnalytics(
        entity_ref=entity_ref, application_id=application_id, statement_id=statement_id,
        scope=scope, version=version, bank_health_score=metrics.get("bank_health_score"),
        metrics=metrics,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
