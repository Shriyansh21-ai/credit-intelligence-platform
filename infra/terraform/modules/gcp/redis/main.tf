variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }
variable "network_id" { type = string }
variable "redis" {
  type = object({
    node_size = string
    num_nodes = number
  })
}
variable "redis_version" {
  type    = string
  default = "REDIS_7_0"
}
variable "labels" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"

  memory_map = {
    small  = 1
    medium = 4
    large  = 8
    xlarge = 16
  }
  memory_size_gb = lookup(local.memory_map, var.redis.node_size, tonumber(var.redis.node_size))

  # More than one node implies a replicated, highly-available topology.
  tier = var.redis.num_nodes > 1 ? "STANDARD_HA" : "BASIC"
}

resource "google_redis_instance" "this" {
  project        = var.gcp_project_id
  name           = "${local.prefix}-redis"
  region         = var.region
  tier           = local.tier
  memory_size_gb = local.memory_size_gb
  redis_version  = var.redis_version

  authorized_network      = var.network_id
  connect_mode            = "PRIVATE_SERVICE_ACCESS"
  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  replica_count = var.redis.num_nodes > 1 ? var.redis.num_nodes - 1 : null

  labels = var.labels
}

output "redis_endpoint" {
  value     = "${google_redis_instance.this.host}:${google_redis_instance.this.port}"
  sensitive = true
}
output "redis_host" {
  value     = google_redis_instance.this.host
  sensitive = true
}
output "redis_port" { value = google_redis_instance.this.port }
output "redis_auth_string" {
  value     = google_redis_instance.this.auth_string
  sensitive = true
}
