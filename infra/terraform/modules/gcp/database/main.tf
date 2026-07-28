variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }
variable "network_id" { type = string }
variable "database" {
  type = object({
    engine_version    = string
    instance_size     = string
    storage_gb        = number
    high_availability = bool
  })
}
variable "db_name" {
  type    = string
  default = "appdb"
}
variable "db_user" {
  type    = string
  default = "appuser"
}
variable "db_password" {
  type      = string
  sensitive = true
}
variable "labels" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"

  version_map = {
    "13" = "POSTGRES_13"
    "14" = "POSTGRES_14"
    "15" = "POSTGRES_15"
    "16" = "POSTGRES_16"
  }
  db_version = lookup(local.version_map, var.database.engine_version, var.database.engine_version)

  tier_map = {
    small  = "db-custom-1-3840"
    medium = "db-custom-2-8192"
    large  = "db-custom-4-16384"
    xlarge = "db-custom-8-32768"
  }
  tier = lookup(local.tier_map, var.database.instance_size, var.database.instance_size)
}

resource "google_compute_global_address" "private_ip" {
  project       = var.gcp_project_id
  name          = "${local.prefix}-db-psa"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = var.network_id
}

resource "google_service_networking_connection" "this" {
  network                 = var.network_id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

resource "google_sql_database_instance" "this" {
  project             = var.gcp_project_id
  name                = "${local.prefix}-pg"
  region              = var.region
  database_version    = local.db_version
  deletion_protection = false

  depends_on = [google_service_networking_connection.this]

  settings {
    tier              = local.tier
    availability_type = var.database.high_availability ? "REGIONAL" : "ZONAL"
    disk_size         = var.database.storage_gb
    disk_type         = "PD_SSD"
    disk_autoresize   = true
    user_labels       = var.labels

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
  }
}

resource "google_sql_database" "this" {
  project  = var.gcp_project_id
  name     = var.db_name
  instance = google_sql_database_instance.this.name
}

resource "google_sql_user" "this" {
  project  = var.gcp_project_id
  name     = var.db_user
  instance = google_sql_database_instance.this.name
  password = var.db_password
}

output "database_endpoint" {
  value     = google_sql_database_instance.this.private_ip_address
  sensitive = true
}
output "instance_name" { value = google_sql_database_instance.this.name }
output "connection_name" {
  value     = google_sql_database_instance.this.connection_name
  sensitive = true
}
output "database_name" { value = google_sql_database.this.name }
