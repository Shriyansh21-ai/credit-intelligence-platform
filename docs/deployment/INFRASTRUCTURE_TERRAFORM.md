# Infrastructure as Code — Terraform

_Phase 11, M6 — enterprise, modular, multi-cloud IaC for the AI Credit
Intelligence Platform._

This tree provisions the cloud substrate the platform runs on (network,
Kubernetes, managed Postgres, managed Redis, object storage, load balancer,
CDN, DNS, secrets, monitoring, logging). The Kubernetes workloads themselves are
deployed separately via `deploy/k8s` (see M4/M5).

> **No secrets in this tree.** No provider credentials, connection strings, or
> keys are committed. Authentication uses the cloud CLIs / OIDC; all sensitive
> outputs are marked `sensitive = true`. State is stored in a remote backend
> (examples in `backends/`).

---

## Layout

```
infra/terraform/
├── README.md
├── environments/            # composition roots — one per env, `terraform apply` here
│   ├── dev/
│   ├── staging/
│   └── prod/
├── modules/
│   ├── aws/                 # reference cloud — full breadth (11 modules + stack)
│   │   ├── network/ compute/ database/ redis/ storage/
│   │   ├── load_balancer/ cdn/ dns/ secrets/ monitoring/ logging/
│   │   └── stack/           # composes all AWS modules into one platform stack
│   ├── azure/               # AKS-based stack (network/compute/database/redis/storage/stack)
│   └── gcp/                 # GKE-based stack (network/compute/database/redis/storage/stack)
└── backends/                # remote-state backend examples (S3, azurerm, GCS)
```

## Multi-cloud contract

Every cloud's `stack` module exposes the **same inputs and outputs**, so an
environment can switch clouds by changing one `source` line. Inputs:

| Input | Type | Purpose |
|-------|------|---------|
| `project`, `environment`, `region` | string | naming + placement |
| `network_cidr` | string | VPC/VNet CIDR |
| `kubernetes` | object(version, node_min, node_max, node_size) | managed k8s |
| `database` | object(engine_version, instance_size, storage_gb, high_availability) | managed Postgres |
| `redis` | object(node_size, num_nodes) | managed Redis |
| `domain` | string | DNS zone / cert |
| `tags` | map(string) | cost allocation / governance |

Outputs (identical names across clouds): `cluster_name`, `cluster_endpoint`,
`kube_config_command`, `database_endpoint`, `redis_endpoint`, `storage_bucket`,
`network_id`. `instance_size`/`node_size` are abstract tiers mapped to each
cloud's native SKUs inside the module.

## Cloud coverage

- **AWS** is the reference implementation with the full module set (all 11
  domains). It matches the platform's primary EKS deployment story.
- **Azure (AKS)** and **GCP (GKE)** implement the platform-critical core
  (network, compute, database, redis, storage) behind the identical stack
  contract. Peripheral domains (CDN, DNS, secrets, monitoring, logging) follow
  the AWS module pattern 1:1 and are the documented extension path — add them by
  mirroring `modules/aws/<domain>` with the native provider resources.

## Usage

```bash
cd infra/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars   # edit values (no secrets)
cp backend.tf.example backend.tf               # point at your remote state
terraform init -backend-config=../../backends/aws.s3.tfbackend
terraform plan
terraform apply
```

Switch cloud by pointing the environment's `platform` module `source` at
`../../modules/azure/stack` or `../../modules/gcp/stack` and selecting the
matching backend example.

## Conventions

- Terraform `>= 1.6`. Providers pinned with `~>` in each module's `versions.tf`.
- Every resource is tagged/labelled from `var.tags`.
- Modules are single-responsibility and independently reusable.
- `terraform fmt` and `terraform validate` run in CI before any apply (add to
  `.github/workflows/ci.yml` once cloud credentials/OIDC are configured).
