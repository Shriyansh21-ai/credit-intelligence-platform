# AWS database module (Phase 11, M6) — RDS for PostgreSQL.
# Private (no public access), encrypted at rest with KMS, automated backups,
# optional Multi-AZ. The master password is generated and stored in Secrets
# Manager — never rendered into state output in plaintext beyond `sensitive`.

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
variable "engine_version" {
  type    = string
  default = "16.4"
}
variable "instance_class" {
  type    = string
  default = "db.r6g.large"
}
variable "allocated_storage" {
  type    = number
  default = 100
}
variable "high_availability" {
  type    = bool
  default = true
}
variable "db_name" {
  type    = string
  default = "credit_ai"
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals { name = "${var.project}-${var.environment}" }

resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}"
}

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "db" {
  name_prefix = "${local.name}-db-"
  description = "Postgres access"
  vpc_id      = var.vpc_id
  ingress {
    description     = "Postgres from app security groups"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_security_group_ids
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = merge(var.tags, { Name = "${local.name}-db-sg" })
  lifecycle { create_before_destroy = true }
}

resource "aws_kms_key" "db" {
  description             = "${local.name} RDS encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_db_instance" "this" {
  identifier     = "${local.name}-pg"
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.allocated_storage * 3
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.db.arn

  db_name  = var.db_name
  username = "credit_admin"
  password = random_password.master.result

  multi_az               = var.high_availability
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false

  backup_retention_period    = 14
  backup_window              = "03:00-04:00"
  maintenance_window         = "Mon:04:00-Mon:05:00"
  auto_minor_version_upgrade = true
  deletion_protection        = var.environment == "prod"
  skip_final_snapshot        = var.environment != "prod"
  final_snapshot_identifier  = var.environment == "prod" ? "${local.name}-pg-final" : null

  performance_insights_enabled    = true
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  copy_tags_to_snapshot           = true
  apply_immediately               = false
  tags                            = var.tags
}

resource "aws_secretsmanager_secret" "db" {
  name                    = "${local.name}/database/credentials"
  recovery_window_in_days = 7
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = aws_db_instance.this.username
    password = random_password.master.result
    host     = aws_db_instance.this.address
    port     = aws_db_instance.this.port
    dbname   = var.db_name
  })
}

output "database_endpoint" {
  value     = aws_db_instance.this.endpoint
  sensitive = true
}
output "database_security_group_id" { value = aws_security_group.db.id }
output "credentials_secret_arn" { value = aws_secretsmanager_secret.db.arn }
