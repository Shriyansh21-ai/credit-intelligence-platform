# Performance Benchmark Report

Date: 2026-08-01
Scope: API endpoint latency and pure-engine compute benchmarks for the AI Credit
Intelligence Platform.

## Methodology

Benchmarks were run against a warm, in-process FastAPI application instance to isolate
application and engine cost from network and cold-start variance. Endpoints selected are
deterministic security and compliance read paths that are representative of compute-heavy
read traffic; their outputs depend only on configuration and repository state, making
repeated measurements stable and reproducible. Latency is reported as p50 and p95 across
repeated single-request measurements; throughput is reported as requests per second on a
single thread. Pure-engine measurements bypass the HTTP and database layers entirely to
report the compute cost of the underlying assessment engines.

## API Endpoint Latency

Single-request latency for deterministic security and compliance endpoints, representative
of compute-heavy read paths.

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

## Pure Engine Compute

Compute cost of the underlying assessment engines with no HTTP or database involvement.

| Engine | mean (ms) | p95 (ms) |
|---|---|---|
| posture.security_posture (aggregates 12 dimensions incl. file reads) | 8.41 | 10.78 |
| owasp.owasp_assessment | 0.02 | 0.02 |
| compliance.compliance_matrix | 0.07 | 0.11 |
| threat_model.build_threat_model | 0.02 | 0.02 |

## Interpretation

The compute-heavy read paths complete comfortably under a sub-60ms p95 envelope across the
board, with the majority of endpoints settling below 25ms p95. The pure catalog engines
(OWASP assessment, compliance matrix, threat model) execute in sub-millisecond time,
confirming that the assessment logic itself carries negligible cost and that observed
endpoint latency is dominated by request handling, serialization, and I/O rather than
computation.

The posture engine is the heaviest compute path at 8.41ms mean and 10.78ms p95 because it
aggregates 12 distinct dimensions, including on-disk file reads, into a single response.
This is reflected at the endpoint level, where the posture and posture-dashboard routes sit
at the upper end of the latency range. Even so, these remain within the sub-60ms p95 band.

## Production Considerations

These figures are drawn from a single warm in-process instance without a caching layer and
on a single worker. In production, response caching for deterministic read paths and
multiple uvicorn workers backed by a pooled PostgreSQL connection pool would materially
raise sustained throughput and reduce tail latency under concurrency.

## Conclusion

The platform delivers sub-60ms p95 latency on compute-heavy read paths and sub-millisecond
execution for its pure catalog engines. The heaviest aggregate path, posture, remains within
budget at roughly 8ms of engine compute across 12 dimensions. Performance is well within
enterprise read-path expectations, with clear headroom available through caching and
horizontal scaling in production.
