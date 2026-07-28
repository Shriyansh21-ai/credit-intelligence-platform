# Development environment composition root (Phase 11, M6).
#
#   terraform init -backend-config=../../backends/aws.s3.tfbackend
#   terraform plan && terraform apply
#
# Switch cloud by pointing module.platform.source at ../../modules/azure/stack
# or ../../modules/gcp/stack and selecting the matching backend example. The
# module contract is identical, so only the source line and provider change.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
  backend "s3" {} # configured via -backend-config=../../backends/aws.s3.tfbackend
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

variable "project" {
  type    = string
  default = "ai-credit"
}
variable "environment" {
  type    = string
  default = "dev"
}
variable "region" {
  type    = string
  default = "us-east-1"
}
variable "domain" {
  type    = string
  default = ""
}
variable "alert_emails" {
  type    = list(string)
  default = []
}

module "platform" {
  source       = "../../modules/aws/stack"
  project      = var.project
  environment  = var.environment
  region       = var.region
  network_cidr = "10.20.0.0/16"

  # Cost-optimised, non-HA for development.
  single_nat_gateway = true
  kubernetes = {
    version   = "1.30"
    node_min  = 1
    node_max  = 3
    node_size = "m6i.large"
  }
  database = {
    engine_version    = "16.4"
    instance_size     = "db.t4g.medium"
    storage_gb        = 20
    high_availability = false
  }
  redis = {
    node_size = "cache.t4g.small"
    num_nodes = 1
  }
  domain       = var.domain
  alert_emails = var.alert_emails
  tags         = { CostCenter = "engineering" }
}

output "cluster_name" { value = module.platform.cluster_name }
output "kube_config_command" { value = module.platform.kube_config_command }
output "storage_bucket" { value = module.platform.storage_bucket }
output "cdn_domain_name" { value = module.platform.cdn_domain_name }
