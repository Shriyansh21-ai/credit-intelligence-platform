variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "region" {
  type = string
}

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

variable "domain" {
  type    = string
  default = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  common_tags = merge(var.tags, {
    project     = var.project
    environment = var.environment
    domain      = var.domain
    managed_by  = "terraform"
  })
}

module "network" {
  source       = "../network"
  project      = var.project
  environment  = var.environment
  region       = var.region
  network_cidr = var.network_cidr
  tags         = local.common_tags
}

module "compute" {
  source              = "../compute"
  project             = var.project
  environment         = var.environment
  region              = var.region
  resource_group_name = module.network.resource_group_name
  aks_subnet_id       = module.network.aks_subnet_id
  kubernetes          = var.kubernetes
  tags                = local.common_tags
}

module "database" {
  source              = "../database"
  project             = var.project
  environment         = var.environment
  region              = var.region
  resource_group_name = module.network.resource_group_name
  delegated_subnet_id = module.network.database_subnet_id
  virtual_network_id  = module.network.network_id
  database            = var.database
  tags                = local.common_tags
}

module "redis" {
  source              = "../redis"
  project             = var.project
  environment         = var.environment
  region              = var.region
  resource_group_name = module.network.resource_group_name
  redis               = var.redis
  tags                = local.common_tags
}

module "storage" {
  source              = "../storage"
  project             = var.project
  environment         = var.environment
  region              = var.region
  resource_group_name = module.network.resource_group_name
  tags                = local.common_tags
}

output "cluster_name" {
  value = module.compute.cluster_name
}

output "cluster_endpoint" {
  value     = module.compute.cluster_endpoint
  sensitive = true
}

output "kube_config_command" {
  value = "az aks get-credentials --resource-group ${module.network.resource_group_name} --name ${module.compute.cluster_name} --overwrite-existing"
}

output "database_endpoint" {
  value     = module.database.database_endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = module.redis.redis_endpoint
  sensitive = true
}

output "storage_bucket" {
  value = module.storage.storage_account_name
}

output "network_id" {
  value = module.network.network_id
}
