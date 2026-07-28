# AWS secrets module (Phase 11, M6) — KMS CMK + Secrets Manager entries with
# automatic rotation scheduling. Backs the application's SecretsProvider
# abstraction (M8). No secret *values* are set here — only the encrypted
# containers and rotation policy; values are written out-of-band or by rotation.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "secret_names" {
  type        = list(string)
  default     = ["app/jwt-signing-key", "app/encryption-key", "app/service-tokens"]
  description = "Logical secret names to provision containers for."
}
variable "rotation_days" {
  type    = number
  default = 90
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals { name = "${var.project}-${var.environment}" }

resource "aws_kms_key" "secrets" {
  description             = "${local.name} application secrets CMK"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${local.name}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

resource "aws_secretsmanager_secret" "this" {
  for_each                = toset(var.secret_names)
  name                    = "${local.name}/${each.value}"
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 7
  tags                    = merge(var.tags, { Rotation = "${var.rotation_days}d" })
}

output "kms_key_arn" { value = aws_kms_key.secrets.arn }
output "kms_alias" { value = aws_kms_alias.secrets.name }
output "secret_arns" {
  value = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}
