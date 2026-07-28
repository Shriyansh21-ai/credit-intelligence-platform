# AWS dns module (Phase 11, M6) — Route53 hosted zone, an ACM certificate with
# DNS validation, and an alias record pointing the apex/host at the ALB.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "domain" {
  type    = string
  default = ""
}
variable "create_zone" {
  type    = bool
  default = true
}
variable "tags" {
  type    = map(string)
  default = {}
}

# The apex alias record that points the domain at the ALB is created by the
# stack (not here) to avoid a dns<->load_balancer module dependency cycle: the
# ALB needs this module's certificate_arn, so this module must not depend on the
# ALB in turn.
locals {
  enabled = var.domain != ""
}

resource "aws_route53_zone" "this" {
  count = local.enabled && var.create_zone ? 1 : 0
  name  = var.domain
  tags  = var.tags
}

data "aws_route53_zone" "existing" {
  count        = local.enabled && !var.create_zone ? 1 : 0
  name         = var.domain
  private_zone = false
}

locals {
  zone_id = local.enabled ? (var.create_zone ? aws_route53_zone.this[0].zone_id : data.aws_route53_zone.existing[0].zone_id) : ""
}

resource "aws_acm_certificate" "this" {
  count                     = local.enabled ? 1 : 0
  domain_name               = var.domain
  subject_alternative_names = ["*.${var.domain}"]
  validation_method         = "DNS"
  tags                      = var.tags
  lifecycle { create_before_destroy = true }
}

resource "aws_route53_record" "validation" {
  for_each = local.enabled ? {
    for dvo in aws_acm_certificate.this[0].domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  } : {}
  zone_id = local.zone_id
  name    = each.value.name
  type    = each.value.type
  records = [each.value.record]
  ttl     = 60
}

resource "aws_acm_certificate_validation" "this" {
  count                   = local.enabled ? 1 : 0
  certificate_arn         = aws_acm_certificate.this[0].arn
  validation_record_fqdns = [for r in aws_route53_record.validation : r.fqdn]
}

resource "aws_route53_record" "apex" {
  count   = local.alias_on ? 1 : 0
  zone_id = local.zone_id
  name    = var.domain
  type    = "A"
  alias {
    name                   = var.alb_dns_name
    zone_id                = var.alb_zone_id
    evaluate_target_health = true
  }
}

output "zone_id" { value = local.zone_id }
output "certificate_arn" { value = local.enabled ? aws_acm_certificate.this[0].arn : "" }
output "name_servers" { value = local.enabled && var.create_zone ? aws_route53_zone.this[0].name_servers : [] }
