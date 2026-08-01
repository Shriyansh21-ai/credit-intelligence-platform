# Consolidated Benchmark Report

Date: 2026-08-01
Scope: Cross-cutting benchmark of API latency, engine execution, database scale, and
throughput for the AI Credit Intelligence Platform.

## Overview

This report consolidates the platform's performance characteristics across four dimensions:
API endpoint latency, pure-engine execution cost, database scale, and single-thread
throughput. All measurements were produced by a deterministic, reproducible benchmark
harness running against a warm, in-process FastAPI application instance. The harness
exercises deterministic endpoints whose outputs depend only on configuration and repository
state, so repeated runs yield stable, comparable figures.

## Headline Numbers

| Metric | Value |
|---|---|
| Best endpoint p95 latency | 18.1 ms (GET /api/sec/compliance/matrix) |
| Heaviest endpoint p95 latency | 57.3 ms (GET /api/sec/posture/dashboard) |
| Fastest pure engine p95 | 0.02 ms (owasp / threat model) |
| Heaviest pure engine p95 | 10.78 ms (posture, 12 dimensions) |
| Peak single-thread throughput | 67.2 rps (compliance matrix) |
| ORM tables | 220 |
| Database indexes | 877 |

## API Endpoint Latency

| Endpoint | p50 (ms) | p95 (ms) | throughput (rps, single-thread) |
|---|---|---|---|
| GET /api/sec/posture | 23.7 | 31.2 | 30.5 |
| GET /api/sec/owasp | 15.3 | 19.0 | 64.8 |
| GET /api/sec/compliance/matrix | 14.8 | 18.1 | 67.2 |
| GET /api/sec/threat | 14.9 | 18.7 | 65.4 |
| GET /api/sec/supply-chain | 18.0 | 24.7 | 54.0 |
| GET /api/sec/posture/dashboard | 32.0 | 57.3 | 27.3 |
| POST /api/sec/scans (owasp) | 31.9 | 46.4 | 24.9 |
| GET /api/sec/findings | 27.2 | 32.7 | 36.0 |

## Engine Execution

| Engine | mean (ms) | p95 (ms) |
|---|---|---|
| posture.security_posture (aggregates 12 dimensions incl. file reads) | 8.41 | 10.78 |
| owasp.owasp_assessment | 0.02 | 0.02 |
| compliance.compliance_matrix | 0.07 | 0.11 |
| threat_model.build_threat_model | 0.02 | 0.02 |

Pure engine compute is sub-millisecond for the catalog-derived assessments and single-digit
milliseconds for the multi-dimension posture aggregation. Endpoint latency is therefore
dominated by request handling and serialization rather than assessment logic.

## Database Scale

| Attribute | Value |
|---|---|
| ORM tables | 220 |
| Indexes | 877 |
| Tables carrying tenant_id | 140 |
| Alembic migrations | 22 (single head c3d4e5f6a7b8) |

The schema is managed exclusively by versioned migrations, with no runtime create_all in the
production path. The upgrade to downgrade to upgrade round-trip has been verified clean. The
877 indexes back scoped multi-tenant queries and foreign-key lookups across the 220-table
model.

## Throughput

On a single thread, the deterministic read endpoints sustain between roughly 25 and 67
requests per second, with the lightest catalog endpoints (compliance matrix, OWASP, threat)
at the top of the range and the compute-heaviest aggregate paths (posture dashboard,
scan creation) at the lower end. These figures represent a single worker without caching and
scale horizontally in production.

## Reproducibility

The benchmark harness is deterministic and reproducible: it targets endpoints whose results
are a pure function of configuration and repository state, applies warmup before measurement,
and reports fixed percentile statistics. Re-running the harness on an unchanged build
reproduces the same figures within measurement noise.

## Conclusion

Across API latency, engine execution, database scale, and throughput, the platform shows
consistent, predictable performance: sub-60ms p95 on all measured read paths, sub-millisecond
catalog engines, and a well-indexed 220-table schema. The deterministic harness makes these
results reproducible and suitable as a regression baseline.
