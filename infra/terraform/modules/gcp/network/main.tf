variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }
variable "network_cidr" {
  type    = string
  default = "10.20.0.0/16"
}
variable "pods_cidr" {
  type    = string
  default = "10.21.0.0/16"
}
variable "services_cidr" {
  type    = string
  default = "10.22.0.0/20"
}

locals {
  prefix = "${var.project}-${var.environment}"
}

resource "google_compute_network" "this" {
  project                 = var.gcp_project_id
  name                    = "${local.prefix}-vpc"
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
}

resource "google_compute_subnetwork" "this" {
  project                  = var.gcp_project_id
  name                     = "${local.prefix}-subnet"
  region                   = var.region
  network                  = google_compute_network.this.id
  ip_cidr_range            = var.network_cidr
  private_ip_google_access = true

  secondary_ip_range {
    range_name    = "${local.prefix}-pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "${local.prefix}-services"
    ip_cidr_range = var.services_cidr
  }
}

resource "google_compute_router" "this" {
  project = var.gcp_project_id
  name    = "${local.prefix}-router"
  region  = var.region
  network = google_compute_network.this.id
}

resource "google_compute_router_nat" "this" {
  project                            = var.gcp_project_id
  name                               = "${local.prefix}-nat"
  router                             = google_compute_router.this.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

resource "google_compute_firewall" "internal" {
  project = var.gcp_project_id
  name    = "${local.prefix}-allow-internal"
  network = google_compute_network.this.id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow { protocol = "icmp" }

  source_ranges = [var.network_cidr, var.pods_cidr, var.services_cidr]
}

resource "google_compute_firewall" "health_checks" {
  project = var.gcp_project_id
  name    = "${local.prefix}-allow-health-checks"
  network = google_compute_network.this.id

  allow {
    protocol = "tcp"
  }

  source_ranges = ["35.191.0.0/16", "130.211.0.0/22"]
}

output "network_id" { value = google_compute_network.this.id }
output "network_self_link" { value = google_compute_network.this.self_link }
output "subnet_id" { value = google_compute_subnetwork.this.id }
output "subnet_self_link" { value = google_compute_subnetwork.this.self_link }
output "pods_range_name" { value = "${local.prefix}-pods" }
output "services_range_name" { value = "${local.prefix}-services" }
