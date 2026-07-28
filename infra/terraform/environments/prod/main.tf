# Production environment composition root (Phase 11, M6).
#   terraform init -backend-config=../../backends/aws.s3.tfbackend
#
# HA everywhere; deletion protection on stateful resources is enabled inside the
# modules when environment == "prod".

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
  backend "s3" {}
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
  default = "prod"
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
  network_cidr = "10.22.0.0/16"

  single_nat_gateway = false
  kubernetes = {
    version   = "1.30"
    node_min  = 4
    node_max  = 12
    node_size = "m6i.2xlarge"
  }
  database = {
    engine_version    = "16.4"
    instance_size     = "db.r6g.2xlarge"
    storage_gb        = 500
    high_availability = true
  }
  redis = {
    node_size = "cache.r6g.xlarge"
    num_nodes = 3
  }
  domain       = var.domain
  alert_emails = var.alert_emails
  tags         = { CostCenter = "production", Compliance = "pci-dss" }
}

output "cluster_name" { value = module.platform.cluster_name }
output "kube_config_command" { value = module.platform.kube_config_command }
output "storage_bucket" { value = module.platform.storage_bucket }
output "cdn_domain_name" { value = module.platform.cdn_domain_name }
