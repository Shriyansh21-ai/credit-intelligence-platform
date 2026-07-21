"""Alert engine — run the early-warning rules over a feature set."""

from __future__ import annotations

from typing import Any, Mapping

from backend.app.services.ml.inference import features_to_mapping

from .rules import RULES, SEVERITY_PRIORITY


def scan(features: Any, engine_input: Mapping | None = None) -> dict:
    """Evaluate every rule and return prioritised alerts + a summary.

    ``features`` may be a feature-vector payload, a feature list or a bare
    ``{name: value}`` mapping. ``engine_input`` is the raw assessment context
    (optional; some rules read banking-conduct fields from it).
    """
    mapping = features_to_mapping(features)
    ctx = dict(engine_input or {})

    alerts = []
    for rule in RULES:
        alert = rule(mapping, ctx)
        if alert is not None:
            alerts.append(alert)

    alerts.sort(key=lambda a: a.priority)
    alert_dicts = [a.as_dict() for a in alerts]

    by_severity = {sev: 0 for sev in SEVERITY_PRIORITY}
    for a in alerts:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1

    return {
        "alerts": alert_dicts,
        "alert_count": len(alert_dicts),
        "highest_severity": alerts[0].severity if alerts else None,
        "by_severity": by_severity,
    }
