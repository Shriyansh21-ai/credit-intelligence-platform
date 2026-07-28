# AWS cdn module (Phase 11, M6) — CloudFront distribution fronting the ALB for
# the SPA/static assets and API edge caching. TLS via the provided ACM cert
# (must be in us-east-1 for CloudFront). API paths are pass-through (no cache).

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "origin_domain_name" {
  type        = string
  description = "ALB DNS name to use as the CloudFront origin."
}
variable "aliases" {
  type    = list(string)
  default = []
}
variable "certificate_arn" {
  type    = string
  default = ""
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  name        = "${var.project}-${var.environment}"
  custom_cert = var.certificate_arn != "" && length(var.aliases) > 0
}

resource "aws_cloudfront_distribution" "this" {
  enabled         = true
  is_ipv6_enabled = true
  comment         = "${local.name} edge"
  aliases         = var.aliases
  price_class     = "PriceClass_100"

  origin {
    domain_name = var.origin_domain_name
    origin_id   = "alb"
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    forwarded_values {
      query_string = true
      cookies { forward = "none" }
    }
    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  # API is dynamic — forward everything, cache nothing.
  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "alb"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Host", "Origin"]
      cookies { forward = "all" }
    }
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.custom_cert ? false : true
    acm_certificate_arn            = local.custom_cert ? var.certificate_arn : null
    ssl_support_method             = local.custom_cert ? "sni-only" : null
    minimum_protocol_version       = local.custom_cert ? "TLSv1.2_2021" : null
  }

  tags = var.tags
}

output "cdn_domain_name" { value = aws_cloudfront_distribution.this.domain_name }
output "cdn_distribution_id" { value = aws_cloudfront_distribution.this.id }
