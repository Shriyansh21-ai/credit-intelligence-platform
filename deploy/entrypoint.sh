#!/usr/bin/env sh
# Container entrypoint (Phase 8, M11).
# Applies Alembic migrations (the single source of truth for schema) then execs
# the passed command. Migrations are idempotent, so this is safe to run on every
# replica start; use an init-container / job in k8s to run it once if preferred.
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] applying database migrations..."
  alembic upgrade head || echo "[entrypoint] migration step skipped/failed (continuing)"
fi

echo "[entrypoint] starting: $*"
exec "$@"
