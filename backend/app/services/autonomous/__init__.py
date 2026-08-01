"""Autonomous AI Banking Intelligence Platform.

The "AI Brain" of the platform. Fully additive over Phases 1-8: it consumes the
existing deterministic assessment engine, financial-analysis engine, ML platform
connectors and SaaS platform, and never mutates their logic.

Sub-packages (one per milestone group)

    graph/ M1 Enterprise Knowledge Graph
    monitoring/ M2 Real-Time Risk Monitoring
    ews/ M3 Early Warning Signal Engine
    copilot/ M4 AI Credit Copilot (+ pluggable LLM adapter)
    simulation/ M5 Scenario Simulation Engine
    stress/ M6 Stress Testing Framework
    optimization/ M7 Portfolio Optimization AI
    rm/ M8 Relationship Manager Workspace
    command/ M9 Executive Command Center
    nlq/ M10 Natural Language Analytics
    recommendations/M11 Enterprise Recommendation Engine
    workflow/ M12 Autonomous Workflow Intelligence
    governance/ M13 Model Governance Platform
    datalake/ M14 Enterprise Data Lake

Shared building blocks live in :mod:`common` (numeric helpers, severity bands
priority scoring) and :mod:`data_access` (read-only loaders over existing tables).
"""

from __future__ import annotations
