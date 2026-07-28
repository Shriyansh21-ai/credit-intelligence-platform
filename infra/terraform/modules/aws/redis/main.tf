# AWS redis module (Phase 11, M6) — ElastiCache for Redis (replication group).
# In-transit + at-rest encryption on, multi-AZ with automatic failover when
# more than one node is requested.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.50" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "allowed_security_group_ids" {
  type    = list(string)
  default = []
}
variable "node_type" {
  type    = string
  default = "cache.r6g.large"
}
variable "num_nodes" {
  type    = number
  default = 2
}
variable "engine_version" {
  type    = string
  default = "7.1"
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  name         = "${var.project}-${var.environment}"
  multi_az     = var.num_nodes > 1
  auth_enabled = true
}

resource "aws_elasticache_subnet_group" "this" {
  name       = "${local.name}-redis"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  description = "Redis access"
  vpc_id      = var.vpc_id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${local.name}-redis-sg" })
  lifecycle { create_before_destroy = true }
}

resource "random_password" "auth" {
  length  = 48
  special = false
}

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${local.name}-redis"
  description          = "${local.name} Redis"
  engine               = "redis"
  engine_version       = var.engine_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_nodes
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.redis.id]

  automatic_failover_enabled = local.multi_az
  multi_az_enabled           = local.multi_az

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.auth.result

  snapshot_retention_limit = 7
  snapshot_window          = "02:00-03:00"
  maintenance_window       = "mon:03:30-mon:04:30"
  apply_immediately        = false
  tags                     = var.tags
}

output "redis_endpoint" {
  value     = aws_elasticache_replication_group.this.primary_endpoint_address
  sensitive = true
}
output "redis_security_group_id" { value = aws_security_group.redis.id }
output "redis_auth_token" {
  value     = random_password.auth.result
  sensitive = true
}

terraform {
  # random provider used above.
  required_providers {
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}
