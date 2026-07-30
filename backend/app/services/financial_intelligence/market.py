"""M6 — Market Intelligence Platform.

Market data & intelligence: interest/yield curves, bond yields, equity indices,
commodities, FX, credit spreads, CDS and volatility, plus corporate/industry/
macro news with sentiment, summaries and impact analysis, and an economic
calendar. The architecture is provider-agnostic: instruments and quotes are
stored generically (``source`` field) so a live market-data feed can be plugged
in later without schema change. Defaults are deterministic synthetic series.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.financial_intelligence import (
    FinMarketInstrument, FinMarketNews, FinMarketQuote,
)
from .common import (
    DeterministicRNG, clamp, iso, linear_interp, mean, pct, safe_div, to_float, utcnow,
)

ASSET_CLASSES = ["rate", "bond", "equity", "commodity", "fx", "credit", "volatility"]
NEWS_CATEGORIES = ["corporate", "industry", "macro"]

# Seed instruments spanning every asset class (symbol, name, class, value).
DEFAULT_INSTRUMENTS = [
    ("IN_REPO", "RBI Repo Rate", "rate", 6.5),
    ("IN_10Y", "India 10Y G-Sec", "bond", 7.05),
    ("IN_2Y", "India 2Y G-Sec", "bond", 6.85),
    ("NIFTY50", "Nifty 50 Index", "equity", 24000.0),
    ("SENSEX", "BSE Sensex", "equity", 79000.0),
    ("USDINR", "USD/INR", "fx", 83.2),
    ("BRENT", "Brent Crude", "commodity", 80.0),
    ("GOLD", "Gold (INR/10g)", "commodity", 71000.0),
    ("IG_SPREAD", "IG Credit Spread", "credit", 1.4),
    ("HY_SPREAD", "HY Credit Spread", "credit", 4.2),
    ("INDIA_VIX", "India VIX", "volatility", 14.5),
]
# Yield-curve tenors (years) -> default par yields (%).
DEFAULT_CURVE = {0.25: 6.6, 0.5: 6.7, 1: 6.85, 2: 6.9, 3: 6.95, 5: 7.0, 7: 7.05, 10: 7.1, 30: 7.25}


def register_instrument(db: Session, *, symbol: str, name: str, asset_class: str,
                        currency: str = "INR", meta: Optional[dict] = None,
                        tenant_id: Optional[int] = None) -> FinMarketInstrument:
    if asset_class not in ASSET_CLASSES:
        raise ValueError(f"unknown asset_class '{asset_class}'")
    existing = (db.query(FinMarketInstrument)
                .filter(FinMarketInstrument.tenant_id == tenant_id,
                        FinMarketInstrument.symbol == symbol).first())
    if existing:
        return existing
    row = FinMarketInstrument(tenant_id=tenant_id, symbol=symbol, name=name,
                              asset_class=asset_class, currency=currency, meta=meta or {})
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def seed_defaults(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    instruments = 0
    for symbol, name, cls, val in DEFAULT_INSTRUMENTS:
        register_instrument(db, symbol=symbol, name=name, asset_class=cls, tenant_id=tenant_id)
        record_quote(db, symbol=symbol, value=val, asset_class=cls, source="seed",
                     tenant_id=tenant_id)
        instruments += 1
    return {"instruments": instruments}


def list_instruments(db: Session, *, asset_class: Optional[str] = None,
                     tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinMarketInstrument)
    if tenant_id is not None:
        q = q.filter(FinMarketInstrument.tenant_id == tenant_id)
    if asset_class:
        q = q.filter(FinMarketInstrument.asset_class == asset_class)
    return [{"id": i.id, "symbol": i.symbol, "name": i.name, "asset_class": i.asset_class,
             "currency": i.currency} for i in q.order_by(FinMarketInstrument.id).all()]


def record_quote(db: Session, *, symbol: str, value: float, asset_class: Optional[str] = None,
                 change: Optional[float] = None, payload: Optional[dict] = None,
                 as_of: Optional[str] = None, source: str = "synthetic",
                 tenant_id: Optional[int] = None) -> FinMarketQuote:
    row = FinMarketQuote(tenant_id=tenant_id, symbol=symbol, asset_class=asset_class,
                         value=to_float(value), change=change, payload=payload or {},
                         as_of=as_of or iso(utcnow())[:10], source=source)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_quotes(db: Session, *, asset_class: Optional[str] = None,
                  tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinMarketQuote)
    if tenant_id is not None:
        q = q.filter(FinMarketQuote.tenant_id == tenant_id)
    if asset_class:
        q = q.filter(FinMarketQuote.asset_class == asset_class)
    seen: Dict[str, Dict[str, Any]] = {}
    for row in q.order_by(FinMarketQuote.id.desc()).limit(500).all():
        if row.symbol not in seen:
            seen[row.symbol] = {"symbol": row.symbol, "asset_class": row.asset_class,
                                "value": row.value, "change": row.change, "as_of": row.as_of,
                                "source": row.source}
    return list(seen.values())


def yield_curve(db: Session, *, curve: Optional[Dict[str, float]] = None,
                query_tenors: Optional[List[float]] = None,
                tenant_id: Optional[int] = None) -> Dict[str, Any]:
    """Interpolated interest-rate/yield curve with spot points and slope."""
    pts = {float(k): float(v) for k, v in (curve or DEFAULT_CURVE).items()}
    xs = sorted(pts)
    ys = [pts[x] for x in xs]
    query_tenors = query_tenors or [0.5, 1, 2, 5, 10, 30]
    interpolated = {str(t): round(linear_interp(t, xs, ys), 4) for t in query_tenors}
    slope = pts[xs[-1]] - pts[xs[0]]
    return {"tenors": xs, "yields": ys, "interpolated": interpolated,
            "slope_2s10s": round(linear_interp(10, xs, ys) - linear_interp(2, xs, ys), 4),
            "curve_slope": round(slope, 4),
            "shape": "inverted" if slope < 0 else "flat" if abs(slope) < 0.2 else "normal"}


# ---------------------------------------------------------------------------
# News, sentiment & impact
# ---------------------------------------------------------------------------

_POS_WORDS = {"growth", "beat", "upgrade", "profit", "surge", "record", "expansion",
              "strong", "gain", "recovery", "positive", "outperform", "rally"}
_NEG_WORDS = {"loss", "downgrade", "default", "decline", "slump", "recession", "weak",
              "cut", "fraud", "probe", "crisis", "negative", "miss", "layoff", "slowdown"}


def _sentiment(text: str) -> float:
    words = set((text or "").lower().replace(".", " ").replace(",", " ").split())
    pos = len(words & _POS_WORDS)
    neg = len(words & _NEG_WORDS)
    if pos + neg == 0:
        return 0.0
    return round(clamp((pos - neg) / (pos + neg), -1.0, 1.0), 3)


def add_news(db: Session, *, headline: str, category: str = "macro", body: Optional[str] = None,
             subject_ref: Optional[str] = None, source: str = "synthetic",
             published_at: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if category not in NEWS_CATEGORIES:
        raise ValueError(f"unknown category '{category}'")
    sentiment = _sentiment(f"{headline} {body or ''}")
    impact = {
        "direction": "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral",
        "magnitude": round(abs(sentiment), 3),
        "affected": [category] + ([subject_ref] if subject_ref else []),
    }
    summary = (headline if len(headline) <= 140 else headline[:137] + "...")
    row = FinMarketNews(tenant_id=tenant_id, headline=headline, body=body, category=category,
                        subject_ref=subject_ref, sentiment=sentiment, impact=impact,
                        summary=summary, source=source, published_at=published_at or iso(utcnow()))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"news_id": row.id, "headline": headline, "category": category,
            "sentiment": sentiment, "impact": impact, "summary": summary}


def list_news(db: Session, *, category: Optional[str] = None, subject_ref: Optional[str] = None,
              limit: int = 50, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
    q = db.query(FinMarketNews)
    if tenant_id is not None:
        q = q.filter(FinMarketNews.tenant_id == tenant_id)
    if category:
        q = q.filter(FinMarketNews.category == category)
    if subject_ref:
        q = q.filter(FinMarketNews.subject_ref == subject_ref)
    return [{"news_id": n.id, "headline": n.headline, "category": n.category,
             "subject_ref": n.subject_ref, "sentiment": n.sentiment, "impact": n.impact,
             "summary": n.summary, "published_at": n.published_at}
            for n in q.order_by(FinMarketNews.id.desc()).limit(limit).all()]


def market_sentiment(db: Session, *, category: Optional[str] = None,
                     subject_ref: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    news = list_news(db, category=category, subject_ref=subject_ref, limit=200, tenant_id=tenant_id)
    scores = [n["sentiment"] for n in news if n["sentiment"] is not None]
    avg = round(mean(scores), 3) if scores else 0.0
    return {"article_count": len(news), "avg_sentiment": avg,
            "mood": "bullish" if avg > 0.15 else "bearish" if avg < -0.15 else "neutral",
            "positive": sum(1 for s in scores if s > 0.1),
            "negative": sum(1 for s in scores if s < -0.1)}


def economic_calendar(db: Session, *, region: str = "IN", weeks: int = 4) -> Dict[str, Any]:
    """Deterministic upcoming-events calendar (synthetic; provider-swappable)."""
    events = [
        {"event": "RBI Monetary Policy", "importance": "high", "week": 1},
        {"event": "CPI Inflation Print", "importance": "high", "week": 1},
        {"event": "Industrial Production (IIP)", "importance": "medium", "week": 2},
        {"event": "GST Collections", "importance": "medium", "week": 2},
        {"event": "GDP Estimate", "importance": "high", "week": 3},
        {"event": "Trade Balance", "importance": "medium", "week": 3},
        {"event": "PMI Manufacturing", "importance": "medium", "week": 4},
    ]
    return {"region": region, "horizon_weeks": weeks,
            "events": [e for e in events if e["week"] <= weeks]}


def dashboard(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    return {
        "quotes": latest_quotes(db, tenant_id=tenant_id),
        "yield_curve": yield_curve(db, tenant_id=tenant_id),
        "sentiment": market_sentiment(db, tenant_id=tenant_id),
        "calendar": economic_calendar(db),
        "generated_at": iso(utcnow()),
    }
