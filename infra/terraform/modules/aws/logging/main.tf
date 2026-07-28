# AWS logging module (Phase 11, M6) — centralised, encrypted CloudWatch log
# groups with retention, plus a metric filter that turns ERROR log lines into a
# CloudWatch metric the monitoring module can alarm on.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "log_groups" {
  type        = list(string)
  default     = ["backend", "worker", "scheduler"]
  description = "Application log group names to create."
}
variable "retention_days" {
  type    = number
  default = 90
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  name      = "${var.project}-${var.environment}"
  namespace = "${var.project}/${var.environment}"
}

resource "aws_kms_key" "logs" {
  description             = "${local.name} CloudWatch Logs encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_cloudwatch_log_group" "this" {
  for_each          = toset(var.log_groups)
  name              = "/ai-credit/${var.environment}/${each.value}"
  retention_in_days = var.retention_days
  kms_key_id        = aws_kms_key.logs.arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_metric_filter" "errors" {
  for_each       = aws_cloudwatch_log_group.this
  name           = "${replace(each.value.name, "/", "-")}-errors"
  log_group_name = each.value.name
  # Structured logs emit {"level":"error",...}; also catch plain ERROR lines.
  pattern = "?ERROR ?\"\\\"level\\\":\\\"error\\\"\""
  metric_transformation {
    name          = "ErrorCount"
    namespace     = local.namespace
    value         = "1"
    default_value = "0"
  }
}

output "log_group_names" { value = [for lg in aws_cloudwatch_log_group.this : lg.name] }
output "logs_kms_key_arn" { value = aws_kms_key.logs.arn }
output "metrics_namespace" { value = local.namespace }
