"""Enterprise Analyst Copilot.

Generates a professional, bank-grade credit memo by composing the outputs of the
scoring engine, financial analysis, feature store, explainability layer and
early-warning system. It is fully deterministic — NOT an LLM — so every sentence
is traceable to an underlying signal and the memo is auditable end to end.
"""

from .analyst_report import build_report_from_engine_input  # noqa: F401
