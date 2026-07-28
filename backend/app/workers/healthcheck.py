"""Liveness healthcheck for the worker/scheduler containers (Phase 11, M2).

Exits 0 if the process wrote its heartbeat within ``--max-age`` seconds, else 1.
Used as the Docker ``HEALTHCHECK`` command and the Kubernetes exec liveness
probe for the (non-HTTP) worker and scheduler pods.

    python -m backend.app.workers.healthcheck [--max-age SECONDS]
"""

from __future__ import annotations

import argparse
import sys
import time

from backend.app.workers.runtime import HEARTBEAT_FILE


def check(max_age: float, path: str = HEARTBEAT_FILE) -> bool:
    try:
        with open(path) as fh:
            beat = float(fh.read().strip())
    except (OSError, ValueError):
        return False
    return (time.time() - beat) <= max_age


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="worker/scheduler liveness check")
    parser.add_argument("--max-age", type=float, default=60.0,
                        help="max heartbeat age in seconds before unhealthy")
    parser.add_argument("--path", default=HEARTBEAT_FILE)
    args = parser.parse_args(argv)
    return 0 if check(args.max_age, args.path) else 1


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
