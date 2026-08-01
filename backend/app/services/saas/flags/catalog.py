"""Default feature-flag registry.

Pure data seeded into ``feature_flags`` on startup. Flags added here appear for
every tenant with the given default; per-tenant behaviour is layered on via
overrides and rollout. New product features should register here so they can be
dark-launched and rolled out gradually.
"""

from __future__ import annotations

from typing import Any, Dict, List

# key, name, description, enabled, rollout, kind, target_roles, dependencies
FLAGS: List[Dict[str, Any]] = [
    {
        "key": "realtime_dashboards",
        "name": "Real-time dashboards",
        "description": "Live-updating dashboards over WebSockets.",
        "enabled": True, "rollout_percentage": 100.0, "kind": "release",
    },
    {
        "key": "ml_autopilot",
        "name": "ML autopilot",
        "description": "Automatic model retraining suggestions.",
        "enabled": False, "rollout_percentage": 25.0, "kind": "canary",
    },
    {
        "key": "customer360_v2",
        "name": "Customer 360 v2",
        "description": "Next-gen unified customer profile.",
        "enabled": False, "rollout_percentage": 0.0, "kind": "experimental",
    },
    {
        "key": "white_label",
        "name": "White-label branding",
        "description": "Tenant-level theme and domain customisation.",
        "enabled": True, "rollout_percentage": 100.0, "kind": "release",
    },
    {
        "key": "advanced_analytics",
        "name": "Advanced analytics",
        "description": "Executive SaaS analytics dashboards.",
        "enabled": True, "rollout_percentage": 100.0, "kind": "release",
        "dependencies": ["realtime_dashboards"],
    },
]
