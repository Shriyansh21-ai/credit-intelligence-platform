variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }

variable "network_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "kubernetes" {
  type = object({
    version   = string
    node_min  = number
    node_max  = number
    node_size = string
  })
}

variable "database" {
  type = object({
    engine_version    = string
    instance_size     = string
    storage_gb        = number
    high_availability = bool
  })
}

variable "redis" {
  type = object({
    node_size = string
    num_nodes = number
  })
}

variable "db_password" {
  type      = string
  sensitive = true
}

variable "domain" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  # GCP labels must use lowercase alphanumerics, hyphens and underscores only.
  # Sanitize both keys and values so arbitrary tags are safe to apply.
  labels = {
    for k, v in merge(var.tags, {
      environment = var.environment
      project     = var.project
      managed-by  = "terraform"
    }) :
    substr(replace(lower(k), "/[^a-z0-9_-]/", "_"), 0, 63) =>
    substr(replace(lower(v), "/[^a-z0-9_-]/", "_"), 0, 63)
  }
}

module "network" {
  source         = "../network"
  project        = var.project
  environment    = var.environment
  region         = var.region
  gcp_project_id = var.gcp_project_id
  network_cidr   = var.network_cidr
}

module "compute" {
  source              = "../compute"
  project             = var.project
  environment         = var.environment
  region              = var.region
  gcp_project_id      = var.gcp_project_id
  network_id          = module.network.network_id
  subnet_id           = module.network.subnet_id
  pods_range_name     = module.network.pods_range_name
  services_range_name = module.network.services_range_name
  kubernetes          = var.kubernetes
  labels              = local.labels
}

module "database" {
  source         = "../database"
  project        = var.project
  environment    = var.environment
  region         = var.region
  gcp_project_id = var.gcp_project_id
  network_id     = module.network.network_id
  database       = var.database
  db_password    = var.db_password
  labels         = local.labels
}

module "redis" {
  source         = "../redis"
  project        = var.project
  environment    = var.environment
  region         = var.region
  gcp_project_id = var.gcp_project_id
  network_id     = module.network.network_id
  redis          = var.redis
  labels         = local.labels
}

module "storage" {
  source         = "../storage"
  project        = var.project
  environment    = var.environment
  region         = var.region
  gcp_project_id = var.gcp_project_id
  labels         = local.labels
}

output "cluster_name" { value = module.compute.cluster_name }
output "cluster_endpoint" {
  value     = module.compute.cluster_endpoint
  sensitive = true
}
output "kube_config_command" {
  value = "gcloud container clusters get-credentials ${module.compute.cluster_name} --region ${var.region} --project ${var.gcp_project_id}"
}
output "database_endpoint" {
  value     = module.database.database_endpoint
  sensitive = true
}
output "redis_endpoint" {
  value     = module.redis.redis_endpoint
  sensitive = true
}
output "storage_bucket" { value = module.storage.storage_bucket }
output "network_id" { value = module.network.network_id }
