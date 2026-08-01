"""Enterprise AI Risk Intelligence layer.

This package houses the ML-facing architecture that sits *on top of* the
deterministic scoring and financial-analysis engines built in Phases 1-3

    features/ - the enterprise Feature Store

Design principle: the AI layer never replaces banking logic. It turns the
existing, explainable financial signals into reusable, versioned, ML-ready
artifacts and prepares the codebase for future model training without changing
any business logic.
"""
