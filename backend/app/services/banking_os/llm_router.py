"""M9 — Multi-LLM Intelligence Layer.

A provider registry + deterministic router over multiple LLM backends
(OpenAI / Anthropic / Gemini / Llama / Mistral / Azure OpenAI / Ollama / local).
Routing chooses a provider by an explicit *strategy* (cost / latency / quality /
priority / balanced) over the registered providers' economics, with automatic
fallback to the next-best available provider and a guaranteed offline ``local``
backend. Every routing decision is explainable (``routed_reason``) and every
invocation is logged for cost/latency/quality analytics.

Actual network calls to hosted vendors are intentionally *not* performed here
(no credentials, deterministic tests). :func:`complete` uses the Phase 9
deterministic ``local`` engine and records realistic economics; wiring a real
vendor SDK is a drop-in at the ``_invoke`` boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.models.banking_os import LLMInvocation, LLMProvider
from .common import clamp

PROVIDER_KINDS = [
    "openai", "anthropic", "gemini", "llama", "mistral", "azure_openai",
    "ollama", "local",
]
STRATEGIES = ["cost", "latency", "quality", "priority", "balanced"]

# Seed economics for a guaranteed, always-available offline provider.
_LOCAL_DEFAULTS = dict(
    kind="local", model="deterministic-v1", priority=200, cost_per_1k_input=0.0,
    cost_per_1k_output=0.0, avg_latency_ms=5.0, quality_score=0.6,
    capabilities=["chat", "json", "grounding"],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def register_provider(db: Session, *, name: str, kind: str, model: Optional[str] = None,
                      priority: int = 100, cost_per_1k_input: float = 0.0,
                      cost_per_1k_output: float = 0.0, avg_latency_ms: float = 0.0,
                      quality_score: float = 0.5, capabilities: Optional[list] = None,
                      config: Optional[dict] = None, enabled: bool = True,
                      tenant_id: Optional[int] = None) -> LLMProvider:
    if kind not in PROVIDER_KINDS:
        raise ValueError(f"unknown provider kind '{kind}'")
    existing = (db.query(LLMProvider)
                .filter(LLMProvider.tenant_id == tenant_id, LLMProvider.name == name).first())
    if existing:
        raise ValueError(f"provider '{name}' already registered")
    p = LLMProvider(tenant_id=tenant_id, name=name, kind=kind, model=model, priority=priority,
                    cost_per_1k_input=cost_per_1k_input, cost_per_1k_output=cost_per_1k_output,
                    avg_latency_ms=avg_latency_ms, quality_score=clamp(quality_score),
                    capabilities=capabilities or ["chat"], config=config or {}, enabled=enabled,
                    is_available=True)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def ensure_local_provider(db: Session, *, tenant_id: Optional[int] = None) -> LLMProvider:
    p = (db.query(LLMProvider)
         .filter(LLMProvider.tenant_id == tenant_id, LLMProvider.kind == "local").first())
    if p is None:
        p = register_provider(db, name="local-deterministic", tenant_id=tenant_id, **_LOCAL_DEFAULTS)
    return p


def update_provider(db: Session, provider_id: int, **fields) -> LLMProvider:
    p = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if p is None:
        raise ValueError("provider not found")
    for k, v in fields.items():
        if hasattr(p, k) and v is not None:
            setattr(p, k, clamp(v) if k == "quality_score" else v)
    db.commit()
    db.refresh(p)
    return p


def list_providers(db: Session, *, tenant_id: Optional[int] = None) -> List[LLMProvider]:
    return (db.query(LLMProvider).filter(LLMProvider.tenant_id == tenant_id)
            .order_by(LLMProvider.priority).all())


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------
def _est_cost(p: LLMProvider, tin: int, tout: int) -> float:
    return round((tin / 1000.0) * p.cost_per_1k_input + (tout / 1000.0) * p.cost_per_1k_output, 6)


def _eligible(providers: List[LLMProvider], capabilities: List[str]) -> List[LLMProvider]:
    out = []
    for p in providers:
        if not p.enabled or not p.is_available:
            continue
        if capabilities and not set(capabilities).issubset(set(p.capabilities or [])):
            continue
        out.append(p)
    return out


def _rank(providers: List[LLMProvider], strategy: str, tin: int, tout: int) -> List[LLMProvider]:
    if strategy == "cost":
        key = lambda p: (_est_cost(p, tin, tout), p.priority)
    elif strategy == "latency":
        key = lambda p: (p.avg_latency_ms, p.priority)
    elif strategy == "quality":
        key = lambda p: (-p.quality_score, p.priority)
    elif strategy == "priority":
        key = lambda p: (p.priority, -p.quality_score)
    else:  # balanced — normalized blend of cost, latency, quality
        costs = [_est_cost(p, tin, tout) for p in providers] or [0.0]
        lats = [p.avg_latency_ms for p in providers] or [0.0]
        max_c, max_l = max(costs) or 1.0, max(lats) or 1.0

        def key(p):
            c = _est_cost(p, tin, tout) / max_c
            l = p.avg_latency_ms / max_l
            # lower is better: cost + latency penalties minus quality reward
            return (round(0.4 * c + 0.3 * l - 0.3 * p.quality_score, 6), p.priority)
    return sorted(providers, key=key)


def route(db: Session, *, strategy: str = "balanced", capabilities: Optional[List[str]] = None,
          est_tokens_in: int = 500, est_tokens_out: int = 500,
          tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy '{strategy}'")
    ensure_local_provider(db, tenant_id=tenant_id)
    capabilities = capabilities or []
    providers = _eligible(list_providers(db, tenant_id=tenant_id), capabilities)
    if not providers:
        raise ValueError("no eligible provider for the requested capabilities")
    ranked = _rank(providers, strategy, est_tokens_in, est_tokens_out)
    chosen = ranked[0]
    fallbacks = ranked[1:]
    return {
        "strategy": strategy,
        "chosen": _provider_brief(chosen, est_tokens_in, est_tokens_out),
        "fallbacks": [_provider_brief(p, est_tokens_in, est_tokens_out) for p in fallbacks],
        "routed_reason": _reason(strategy, chosen, est_tokens_in, est_tokens_out),
    }


def _reason(strategy: str, p: LLMProvider, tin: int, tout: int) -> str:
    if strategy == "cost":
        return f"lowest estimated cost ${_est_cost(p, tin, tout)}"
    if strategy == "latency":
        return f"lowest latency {p.avg_latency_ms}ms"
    if strategy == "quality":
        return f"highest quality {p.quality_score}"
    if strategy == "priority":
        return f"highest priority (rank {p.priority})"
    return "best balanced cost/latency/quality blend"


def _provider_brief(p: LLMProvider, tin: int, tout: int) -> Dict[str, Any]:
    return {"id": p.id, "name": p.name, "kind": p.kind, "model": p.model,
            "est_cost": _est_cost(p, tin, tout), "avg_latency_ms": p.avg_latency_ms,
            "quality_score": p.quality_score, "priority": p.priority}


# ---------------------------------------------------------------------------
# Completion (with fallback) — logged for analytics
# ---------------------------------------------------------------------------
def _invoke(provider: LLMProvider, prompt: str) -> Dict[str, Any]:
    """Perform the actual generation.

    Hosted vendors would call their SDK here at the ``_invoke`` boundary; without
    credentials we synthesize a deterministic, reproducible local completion so
    routing/fallback/analytics are fully testable offline. Returns
    ``{text, tokens_out, quality, success}``.
    """
    text = f"[{provider.kind}:{provider.model or provider.name}] {prompt.strip()[:280]}"
    tokens_out = max(1, len(text.split()))
    return {"text": text, "tokens_out": tokens_out, "quality": provider.quality_score,
            "success": True}


def complete(db: Session, *, prompt: str, strategy: str = "balanced",
             capabilities: Optional[List[str]] = None, prompt_ref: Optional[str] = None,
             tenant_id: Optional[int] = None) -> Dict[str, Any]:
    tin = max(1, len(prompt.split()))
    decision = route(db, strategy=strategy, capabilities=capabilities or [],
                     est_tokens_in=tin, est_tokens_out=tin, tenant_id=tenant_id)
    chain = [decision["chosen"]] + decision["fallbacks"]
    fallback_used = False
    last_err = None
    for i, brief in enumerate(chain):
        provider = db.query(LLMProvider).filter(LLMProvider.id == brief["id"]).first()
        if provider is None:
            continue
        try:
            res = _invoke(provider, prompt)
            cost = _est_cost(provider, tin, res["tokens_out"])
            inv = LLMInvocation(
                tenant_id=tenant_id, provider=provider.name, kind=provider.kind, strategy=strategy,
                prompt_ref=prompt_ref, tokens_in=tin, tokens_out=res["tokens_out"],
                latency_ms=provider.avg_latency_ms, cost=cost, quality=res["quality"],
                success=True, fallback_used=fallback_used,
                routed_reason=decision["routed_reason"] if not fallback_used else "primary failed → fallback")
            db.add(inv)
            db.commit()
            db.refresh(inv)
            return {"provider": provider.name, "kind": provider.kind, "text": res["text"],
                    "tokens_in": tin, "tokens_out": res["tokens_out"], "cost": cost,
                    "latency_ms": provider.avg_latency_ms, "quality": res["quality"],
                    "fallback_used": fallback_used, "strategy": strategy,
                    "routed_reason": decision["routed_reason"], "invocation_id": inv.id,
                    "confidence": round(clamp(res["quality"]), 3)}
        except Exception as ex:  # pragma: no cover - defensive
            last_err = ex
            fallback_used = True
            continue
    raise ValueError(f"all providers failed: {last_err}")


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
def analytics(db: Session, *, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    invs = db.query(LLMInvocation).filter(LLMInvocation.tenant_id == tenant_id).all()
    by_provider: Dict[str, Dict[str, Any]] = {}
    total_cost = 0.0
    for inv in invs:
        b = by_provider.setdefault(inv.provider, {"calls": 0, "cost": 0.0, "tokens_in": 0,
                                                  "tokens_out": 0, "latency_ms": 0.0, "fallbacks": 0})
        b["calls"] += 1
        b["cost"] = round(b["cost"] + inv.cost, 6)
        b["tokens_in"] += inv.tokens_in
        b["tokens_out"] += inv.tokens_out
        b["latency_ms"] += inv.latency_ms
        b["fallbacks"] += 1 if inv.fallback_used else 0
        total_cost += inv.cost
    for b in by_provider.values():
        b["avg_latency_ms"] = round(b["latency_ms"] / b["calls"], 2) if b["calls"] else 0.0
        b.pop("latency_ms", None)
    return {"total_invocations": len(invs), "total_cost": round(total_cost, 6),
            "providers": db.query(LLMProvider).filter(LLMProvider.tenant_id == tenant_id).count(),
            "by_provider": by_provider}


def provider_dict(p: LLMProvider) -> Dict[str, Any]:
    return {"id": p.id, "name": p.name, "kind": p.kind, "model": p.model, "enabled": p.enabled,
            "priority": p.priority, "cost_per_1k_input": p.cost_per_1k_input,
            "cost_per_1k_output": p.cost_per_1k_output, "avg_latency_ms": p.avg_latency_ms,
            "quality_score": p.quality_score, "capabilities": p.capabilities,
            "is_available": p.is_available}
