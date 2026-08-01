# syntax=docker/dockerfile:1.7
# =============================================================================
# AI Credit Intelligence Platform — frontend SSR image (Phase 11, M2)
# =============================================================================
# Build context: the `frontend/` directory.
#   docker build -f frontend/Dockerfile -t ai-credit-frontend ./frontend
#
# Stage 1 builds the TanStack Start app with bun (honoring bun.lock + bunfig).
# Stage 2 serves the SSR fetch-handler build on a slim Node runtime via the
# dependency-free adapter in server/node-server.mjs. Runs as a non-root user.
# -----------------------------------------------------------------------------

# ----------------------------- builder ---------------------------------------
FROM oven/bun:1 AS builder
WORKDIR /app
# Install deps first (cached until manifests change) for fast rebuilds.
COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile
# Then the source, and build the client + SSR bundles into dist/.
COPY . .
RUN bun run build

# ----------------------------- runtime ---------------------------------------
FROM node:22-slim AS runtime
ENV NODE_ENV=production \
    PORT=3000 \
    HOST=0.0.0.0
WORKDIR /app

# Only the build output and the SSR adapter are needed at runtime — no
# node_modules, no source, no bun. Keeps the image small.
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/server ./server

RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 3000

# Node 22 ships a global fetch; no curl needed in the slim image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://localhost:'+ (process.env.PORT||3000) +'/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server/node-server.mjs"]
