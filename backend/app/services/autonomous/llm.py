"""Pluggable LLM orchestration layer for the AI Copilot (M4) and NL analytics (M10).

Mirrors the Phase 7/8 "abstraction with a working local default + gated production
adapter" pattern. The platform NEVER trusts an LLM for numbers: every engine first
assembles *deterministic grounding* from real platform data, and the provider only
phrases/orchestrates that grounding into prose. This module is therefore safe to
run fully offline (the default) and can be upgraded to Claude by setting one env
var — with no change to any call site.

Providers implement :class:`LLMProvider.compose`, which receives the already-computed
grounding and must not invent facts.

    LLMProvider (ABC)
      ├─ LocalDeterministicProvider   default, offline, template-driven
      └─ ClaudeProvider               gated: needs `anthropic` + ANTHROPIC_API_KEY
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def compose(self, *, question: str, grounding: Dict[str, Any], intent: str,
                system: Optional[str] = None) -> str:
        """Render a natural-language answer strictly from ``grounding``."""

    @property
    def available(self) -> bool:  # pragma: no cover - trivial
        return True


# ---------------------------------------------------------------------------
# Local deterministic provider (default) — pure formatting, no network.
# ---------------------------------------------------------------------------
class LocalDeterministicProvider(LLMProvider):
    """Renders grounding into a readable, fully deterministic narrative.

    Guarantees: no value appears in the output that is not present in the
    grounding dict. Ideal for air-gapped banks and reproducible tests.
    """

    name = "local"

    def compose(self, *, question: str, grounding: Dict[str, Any], intent: str,
                system: Optional[str] = None) -> str:
        headline = grounding.get("headline")
        facts: List[Dict[str, Any]] = grounding.get("facts", [])
        narrative = grounding.get("narrative")
        lines: List[str] = []
        if headline:
            lines.append(headline)
        if narrative:
            lines.append(narrative)
        if facts:
            lines.append("")
            for f in facts:
                label = f.get("label", "")
                value = f.get("value")
                if value is None:
                    value = "unavailable"
                lines.append(f"- {label}: {value}")
        actions = grounding.get("recommended_actions") or []
        if actions:
            lines.append("")
            lines.append("Recommended next steps:")
            for a in actions:
                lines.append(f"  • {a}")
        if not lines:
            lines.append("I could not find grounded platform data to answer that. "
                         "Try binding a company or assessment to this conversation.")
        return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Claude provider (gated) — orchestration only, still grounded.
# ---------------------------------------------------------------------------
class ClaudeProvider(LLMProvider):
    """Uses the Anthropic Claude API purely to phrase the supplied grounding.

    Gated behind the ``anthropic`` package + ``ANTHROPIC_API_KEY``. If either is
    missing it reports ``available == False`` and the factory falls back to the
    local provider, so importing this module never fails.
    """

    name = "claude"

    def __init__(self, model: Optional[str] = None):
        from backend.app.core.settings import get_settings
        _s = get_settings()
        self.model = model or _s.llm_model
        self._client = None
        try:  # pragma: no cover - only exercised when SDK+key are present
            import anthropic  # type: ignore
            key = _s.anthropic_api_key
            if key:
                self._client = anthropic.Anthropic(api_key=key)
        except Exception:
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def compose(self, *, question: str, grounding: Dict[str, Any], intent: str,
                system: Optional[str] = None) -> str:
        if not self.available:  # pragma: no cover
            return LocalDeterministicProvider().compose(
                question=question, grounding=grounding, intent=intent, system=system)
        sys = system or (
            "You are an expert senior credit analyst assisting a banking team. "
            "You MUST answer using ONLY the JSON grounding facts provided. Never "
            "invent, estimate or extrapolate numbers. If a fact is missing, say it "
            "is unavailable. Be concise and precise.")
        import json
        content = (f"Question: {question}\n\nGrounding (authoritative, do not deviate):\n"
                   f"{json.dumps(grounding, default=str, indent=2)}")
        try:  # pragma: no cover
            resp = self._client.messages.create(
                model=self.model, max_tokens=800, system=sys,
                messages=[{"role": "user", "content": content}])
            return "".join(getattr(b, "text", "") for b in resp.content).strip()
        except Exception:
            return LocalDeterministicProvider().compose(
                question=question, grounding=grounding, intent=intent, system=system)


_LOCAL = LocalDeterministicProvider()
_CACHE: Dict[str, LLMProvider] = {"local": _LOCAL}


def get_provider(name: Optional[str] = None) -> LLMProvider:
    """Resolve the active provider.

    Order: explicit ``name`` → ``COPILOT_LLM_PROVIDER`` env → ``local``. A requested
    Claude provider that is not actually available degrades to local (never errors).
    """
    from backend.app.core.settings import get_settings
    choice = (name or get_settings().llm_provider or "local").lower()
    if choice in _CACHE:
        return _CACHE[choice]
    if choice == "claude":
        prov: LLMProvider = ClaudeProvider()
        if not prov.available:
            prov = _LOCAL
        _CACHE["claude"] = prov
        return prov
    return _LOCAL


def provider_status() -> Dict[str, Any]:
    active = get_provider()
    claude = ClaudeProvider()
    from backend.app.core.settings import get_settings
    return {"active": active.name, "local_available": True,
            "claude_available": claude.available,
            "configured": get_settings().llm_provider}
