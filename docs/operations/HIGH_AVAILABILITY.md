# High Availability

*How the platform stays available under load and failure — verified topology,
autoscaling and failure-domain design.*

The platform is a **stateless, horizontally-scalable** service fronted by a load
balancer, with state pushed to managed, replicated backing services. Any single
pod or node can fail without downtime.

## Topology (verified)

| Tier | Kubernetes object | HA property |
|------|-------------------|-------------|
| API | `deploy/k8s/base/backend.yaml` | ≥3 replicas, liveness/readiness probes, rolling updates |
| Worker | `deploy/k8s/base/worker.yaml` | ≥2 replicas, queue-driven |
| Scheduler | `deploy/k8s/base/scheduler.yaml` | singleton with leader semantics |
| Edge | `deploy/k8s/base/nginx.yaml` | load-balanced ingress |
| Database | `deploy/k8s/base/postgres.yaml` / managed RDS | replicated, PITR |
| Cache/broker | `deploy/k8s/base/redis.yaml` / managed | replicated |

## Autoscaling (verified — `deploy/k8s/base/hpa.yaml`)

| Workload | Min | Max | Signals |
|----------|-----|-----|---------|
| backend | 3 | 20 | CPU 70% / memory 80%, scale-down stabilization 300s |
| worker | 2 | 10 | CPU 75% |

Horizontal Pod Autoscalers (`autoscaling/v2`) scale on resource utilization with
a scale-down stabilization window to avoid flapping.

## Statelessness & draining

- The API holds **no in-process session state** — auth is JWT, cache/queue are
  external — so any replica can serve any request and pods are replaceable.
- On shutdown, the **readiness probe flips first** (`/readyz`), so Kubernetes
  removes the pod from the Service and drains in-flight requests before
  `SIGTERM` terminates it.
- Rolling updates (`maxSurge`/`maxUnavailable`) keep capacity during deploys;
  blue-green/canary strategies are available via the deployment pipeline.

## Failure domains

- Spread replicas across nodes/zones (topology spread / anti-affinity at the
  cluster level).
- Managed Postgres/Redis provide cross-AZ replication and automated failover.
- Multi-cloud substrate is provisioned by `infra/terraform/` with a uniform
  stack contract per cloud.

## Capacity & scaling

See [Scaling Guide](../deployment/SCALING_GUIDE.md) for capacity planning and
[Performance](PERFORMANCE.md) for the latency/throughput characteristics that
drive the HPA thresholds above.

---

← Back to [Operations Documentation](index.md) ·
See also [Disaster Recovery](DISASTER_RECOVERY.md) ·
[Production Hardening](../deployment/PRODUCTION_HARDENING.md)
