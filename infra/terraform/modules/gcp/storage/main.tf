variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }
variable "bucket_suffix" {
  type    = string
  default = "data"
}
variable "force_destroy" {
  type    = bool
  default = false
}
variable "noncurrent_version_age" {
  type    = number
  default = 30
}
variable "labels" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"
  # Bucket names are globally unique and must be lowercase; scope by project id.
  bucket_name = lower("${local.prefix}-${var.bucket_suffix}-${var.gcp_project_id}")
}

resource "google_storage_bucket" "this" {
  project                     = var.gcp_project_id
  name                        = local.bucket_name
  location                    = var.region
  storage_class               = "STANDARD"
  force_destroy               = var.force_destroy
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age        = var.noncurrent_version_age
      with_state = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 5
    }
    action {
      type = "Delete"
    }
  }

  labels = var.labels
}

output "storage_bucket" { value = google_storage_bucket.this.name }
output "storage_bucket_url" { value = google_storage_bucket.this.url }
output "storage_bucket_self_link" { value = google_storage_bucket.this.self_link }
