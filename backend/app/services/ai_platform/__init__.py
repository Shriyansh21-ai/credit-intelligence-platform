"""AI Intelligence Platform (Track 2).

An additive, production-grade AI layer built on top of every previous phase.
Nothing from Phases 1-11 / Track 1 is modified — the AI platform is *another
layer*, not another application.

Foundation modules (shared by every milestone):
    common       — pure deterministic helpers (text, vectors, hashing)
    embeddings   — pluggable Embedder ABC (offline hashing default)
    vectorstore  — pluggable VectorStore ABC (SQL default, pgvector-ready)
    llm          — instrumented, grounding-first LLM client (offline default)

Milestone services are added module-by-module (rag, agents, memory, prompts,
evaluation, investigation, reports, workflows, chat, research, learning,
governance, explainability, monitoring).
"""

from backend.app.services.ai_platform import common, embeddings, llm, vectorstore  # noqa: F401

# Milestone services (import lazily-safe; each only depends on the foundation +
# earlier milestones + the shared platform read layer).
from backend.app.services.ai_platform import (  # noqa: F401
    agents, ai_monitoring, chat, evaluation, explainability, governance,
    investigation, learning, memory, prompts, rag, reports, research, workflows,
)

__all__ = [
    "common", "embeddings", "vectorstore", "llm",
    "rag", "agents", "memory", "prompts", "evaluation", "investigation",
    "reports", "workflows", "chat", "research", "learning", "governance",
    "explainability", "ai_monitoring",
]
