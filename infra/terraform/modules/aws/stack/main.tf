# AWS platform stack (Phase 11, M6) — composes every AWS module into one
# deployable unit behind the cross-cloud contract. Environments call this (or
# the azure/gcp equivalent) with identical inputs and read identical outputs.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

# ----- Cross-cloud contract inputs (identical across aws/azure/gcp) -----------
variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
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

# ----- AWS-specific knobs -----------------------------------------------------
variable "alert_emails" {
  type    = list(string)
  default = []
}
variable "single_nat_gateway" {
  type    = bool
  default = false
}

locals {
  common_tags = merge(var.tags, {
    Project     = var.project
    Environment = var.environment
    ManagedBy   = "terraform"
  })
}

module "network" {
  source             = "../network"
  project            = var.project
  environment        = var.environment
  network_cidr       = var.network_cidr
  single_nat_gateway = var.single_nat_gateway
  tags               = local.common_tags
}

module "compute" {
  source             = "../compute"
  project            = var.project
  environment        = var.environment
  cluster_version    = var.kubernetes.version
  private_subnet_ids = module.network.private_subnet_ids
  node_min           = var.kubernetes.node_min
  node_max           = var.kubernetes.node_max
  node_instance_type = var.kubernetes.node_size
  tags               = local.common_tags
}

module "database" {
  source                     = "../database"
  project                    = var.project
  environment                = var.environment
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.compute.cluster_security_group_id]
  engine_version             = var.database.engine_version
  instance_class             = var.database.instance_size
  allocated_storage          = var.database.storage_gb
  high_availability          = var.database.high_availability
  tags                       = local.common_tags
}

module "redis" {
  source                     = "../redis"
  project                    = var.project
  environment                = var.environment
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.compute.cluster_security_group_id]
  node_type                  = var.redis.node_size
  num_nodes                  = var.redis.num_nodes
  tags                       = local.common_tags
}

module "storage" {
  source      = "../storage"
  project     = var.project
  environment = var.environment
  tags        = local.common_tags
}

module "secrets" {
  source      = "../secrets"
  project     = var.project
  environment = var.environment
  tags        = local.common_tags
}

module "dns" {
  source      = "../dns"
  project     = var.project
  environment = var.environment
  domain      = var.domain
  tags        = local.common_tags
}

module "load_balancer" {
  source            = "../load_balancer"
  project           = var.project
  environment       = var.environment
  vpc_id            = module.network.vpc_id
  public_subnet_ids = module.network.public_subnet_ids
  certificate_arn   = module.dns.certificate_arn
  tags              = local.common_tags
}

# Apex alias record lives here (not in the dns module) to break the
# dns<->load_balancer dependency cycle.
resource "aws_route53_record" "apex" {
  count   = var.domain != "" ? 1 : 0
  zone_id = module.dns.zone_id
  name    = var.domain
  type    = "A"
  alias {
    name                   = module.load_balancer.alb_dns_name
    zone_id                = module.load_balancer.alb_zone_id
    evaluate_target_health = true
  }
}

module "cdn" {
  source             = "../cdn"
  project            = var.project
  environment        = var.environment
  origin_domain_name = module.load_balancer.alb_dns_name
  tags               = local.common_tags
}

module "logging" {
  source      = "../logging"
  project     = var.project
  environment = var.environment
  tags        = local.common_tags
}

module "monitoring" {
  source                     = "../monitoring"
  project                    = var.project
  environment                = var.environment
  region                     = var.region
  alert_emails               = var.alert_emails
  db_instance_id             = "${var.project}-${var.environment}-pg"
  redis_replication_group_id = "${var.project}-${var.environment}-redis"
  alb_arn_suffix             = module.load_balancer.alb_arn_suffix
  app_metrics_namespace      = module.logging.metrics_namespace
  tags                       = local.common_tags
}

# ----- Cross-cloud contract outputs -------------------------------------------
output "cluster_name" { value = module.compute.cluster_name }
output "cluster_endpoint" {
  value     = module.compute.cluster_endpoint
  sensitive = true
}
output "kube_config_command" {
  value = "aws eks update-kubeconfig --name ${module.compute.cluster_name} --region ${var.region}"
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
output "cdn_domain_name" { value = module.cdn.cdn_domain_name }
output "alerts_topic_arn" { value = module.monitoring.alerts_topic_arn }
