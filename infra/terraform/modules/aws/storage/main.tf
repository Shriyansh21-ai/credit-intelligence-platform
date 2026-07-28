# AWS storage module (Phase 11, M6) — S3 bucket for platform documents/artifacts.
# Private, KMS-encrypted, versioned, TLS-enforced, with lifecycle tiering.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.50" }
  }
}

variable "project" { type = string }
variable "environment" { type = string }
variable "bucket_suffix" {
  type    = string
  default = "documents"
}
variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  name        = "${var.project}-${var.environment}"
  bucket_name = "${local.name}-${var.bucket_suffix}"
}

resource "aws_kms_key" "bucket" {
  description             = "${local.name} S3 encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  tags                    = var.tags
}

resource "aws_s3_bucket" "this" {
  bucket = local.bucket_name
  tags   = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.this.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.bucket.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  bucket                  = aws_s3_bucket.this.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  bucket = aws_s3_bucket.this.id
  rule {
    id     = "tier-and-expire-noncurrent"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 365
      storage_class = "GLACIER"
    }
    noncurrent_version_expiration { noncurrent_days = 180 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

# Deny any non-TLS access.
data "aws_iam_policy_document" "tls_only" {
  statement {
    sid       = "DenyInsecureTransport"
    effect    = "Deny"
    actions   = ["s3:*"]
    resources = [aws_s3_bucket.this.arn, "${aws_s3_bucket.this.arn}/*"]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "tls_only" {
  bucket = aws_s3_bucket.this.id
  policy = data.aws_iam_policy_document.tls_only.json
}

output "storage_bucket" { value = aws_s3_bucket.this.id }
output "storage_bucket_arn" { value = aws_s3_bucket.this.arn }
output "storage_kms_key_arn" { value = aws_kms_key.bucket.arn }
