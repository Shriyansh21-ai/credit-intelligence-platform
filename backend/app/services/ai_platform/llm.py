"""LLM client for the AI Intelligence Platform (Track 2).

Extends the Phase 9 grounding-first philosophy (``services/autonomous/llm.py``)
with a richer, instrumented interface that the agents (M2), reports (M7),
evaluation (M5) and monitoring (M14) layers all need: message-based generation
plus per-call usage (tokens, latency, cost) and a ``grounded`` flag.

The platform NEVER trusts an LLM for facts. Every caller assembles deterministic
``grounding`` from real platform data first; the provider only phrases it. The
default :class:`LocalDeterministicLLM` runs fully offline and reproducibly; the
gated :class:`ClaudeLLM` upgrades phrasing when ``ANTHROPIC_API_KEY`` is set —
with no change to any call site.

    LLMClient (ABC)
      ├─ LocalDeterministicLLM   default, offline, template composition
      └─ ClaudeLLM               gated: needs `anthropic` + ANTHROPIC_API_KEY
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.app.services.ai_platform import common

# Rough public list price ($/1K tokens) used only for cost *estimation* in the
# eval/monitoring layers — never billed. Local provider is always free.
_COST_PER_1K = {"claude": (0.003, 0.015), "local": (0.0, 0.0)}


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    grounded: bool = True
    finish_reason: str = "stop"
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def as_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": common.round_opt(self.latency_ms, 2),
            "cost_usd": common.round_opt(self.cost_usd, 6),
            "grounded": self.grounded,
            "finish_reason": self.finish_reason,
        }


def _estimate_cost(provider: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = _COST_PER_1K.get(provider, (0.0, 0.0))
    return (prompt_tokens / 1000.0) * inp + (completion_tokens / 1000.0) * out


class LLMClient(ABC):
    name = "base"
    model = "base"

    @abstractmethod
    def _compose(self, *, system: str, prompt: str,
                 grounding: Optional[Dict[str, Any]]) -> str: ...

    def generate(self, *, prompt: str = "", system: Optional[str] = None,
                 grounding: Optional[Dict[str, Any]] = None,
                 messages: Optional[List[LLMMessage]] = None,
                 max_tokens: int = 800, temperature: float = 0.0) -> LLMResult:
        sys = system or (
            "You are a senior banking analyst. Answer using ONLY the supplied "
            "grounding facts; never invent numbers. If a fact is missing, say it "
            "is unavailable. Be precise and concise."
        )
        if messages:
            prompt = "\n\n".join(f"{m.role}: {m.content}" for m in messages) or prompt
        started = time.perf_counter()
        text = self._compose(system=sys, prompt=prompt, grounding=grounding)
        latency = (time.perf_counter() - started) * 1000.0
        p_tok = common.token_count(sys) + common.token_count(prompt) + \
            common.token_count(json.dumps(grounding, default=str) if grounding else "")
        c_tok = common.token_count(text)
        return LLMResult(
            text=text, provider=self.name, model=self.model,
            prompt_tokens=p_tok, completion_tokens=c_tok, latency_ms=latency,
            cost_usd=_estimate_cost(self.name, p_tok, c_tok),
            grounded=grounding is not None,
        )

    @property
    def available(self) -> bool:  # pragma: no cover - trivial
        return True


class LocalDeterministicLLM(LLMClient):
    """Renders grounding (headline/narrative/facts/actions/citations) into prose.

    Guarantees no value appears that is not present in ``grounding`` — ideal for
    reproducible tests and air-gapped deployments.
    """

    name = "local"
    model = "local-deterministic"

    def _compose(self, *, system, prompt, grounding) -> str:
        if not grounding:
            # No grounding → return a safe, deterministic acknowledgement rather
            # than fabricating content.
            return (prompt.strip() or
                    "No grounded platform data was supplied for this request.")
        lines: List[str] = []
        headline = grounding.get("headline")
        narrative = grounding.get("narrative")
        if headline:
            lines.append(str(headline))
        if narrative:
            lines.append(str(narrative))
        facts = grounding.get("facts") or []
        if facts:
            lines.append("")
            for f in facts:
                if isinstance(f, dict):
                    label = f.get("label", "")
                    value = f.get("value")
                    lines.append(f"- {label}: {'unavailable' if value is None else value}")
                else:
                    lines.append(f"- {f}")
        actions = grounding.get("recommended_actions") or []
        if actions:
            lines.append("")
            lines.append("Recommended next steps:")
            for a in actions:
                lines.append(f"  • {a}")
        citations = grounding.get("citations") or []
        if citations:
            lines.append("")
            lines.append("Sources:")
            for i, c in enumerate(citations, 1):
                label = c.get("label", c.get("ref_id", "source")) if isinstance(c, dict) else c
                lines.append(f"  [{i}] {label}")
        return "\n".join(lines).strip() or "No grounded data available."


class ClaudeLLM(LLMClient):
    """Gated Anthropic Claude client — phrasing only, still grounded."""

    name = "claude"

    def __init__(self, model: Optional[str] = None):
        from backend.app.core.settings import get_settings
        s = get_settings()
        self.model = model or s.llm_model
        self._client = None
        try:  # pragma: no cover - only with SDK + key present
            import anthropic  # type: ignore
            key = s.anthropic_api_key
            if key:
                self._client = anthropic.Anthropic(api_key=key)
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def _compose(self, *, system, prompt, grounding) -> str:  # pragma: no cover
        if not self.available:
            return LocalDeterministicLLM()._compose(
                system=system, prompt=prompt, grounding=grounding)
        content = prompt
        if grounding:
            content = (f"{prompt}\n\nGrounding (authoritative, do not deviate):\n"
                       f"{json.dumps(grounding, default=str, indent=2)}")
        try:
            resp = self._client.messages.create(
                model=self.model, max_tokens=1024, system=system,
                messages=[{"role": "user", "content": content}])
            return "".join(getattr(b, "text", "") for b in resp.content).strip()
        except Exception:
            return LocalDeterministicLLM()._compose(
                system=system, prompt=prompt, grounding=grounding)


_LOCAL = LocalDeterministicLLM()
_CACHE: Dict[str, LLMClient] = {"local": _LOCAL}


def get_llm(name: Optional[str] = None) -> LLMClient:
    """Resolve the active LLM client.

    Order: explicit ``name`` → ``AIP_LLM_PROVIDER`` → the shared
    ``COPILOT_LLM_PROVIDER`` setting → ``local``. A requested Claude client that
    is not actually available degrades to local, so this never raises.
    """
    from backend.app.core.settings import get_settings
    choice = (name or os.getenv("AIP_LLM_PROVIDER")
              or get_settings().llm_provider or "local").lower()
    if choice in _CACHE:
        return _CACHE[choice]
    if choice == "claude":
        client: LLMClient = ClaudeLLM()
        if not client.available:
            client = _LOCAL
        _CACHE["claude"] = client
        return client
    return _LOCAL


def llm_status() -> Dict[str, Any]:
    active = get_llm()
    claude = ClaudeLLM()
    from backend.app.core.settings import get_settings
    return {
        "active": active.name,
        "model": active.model,
        "local_available": True,
        "claude_available": claude.available,
        "configured": os.getenv("AIP_LLM_PROVIDER") or get_settings().llm_provider,
    }
