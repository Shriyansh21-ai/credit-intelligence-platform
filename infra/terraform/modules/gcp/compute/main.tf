variable "project" { type = string }
variable "environment" { type = string }
variable "region" { type = string }
variable "gcp_project_id" { type = string }
variable "network_id" { type = string }
variable "subnet_id" { type = string }
variable "pods_range_name" { type = string }
variable "services_range_name" { type = string }
variable "master_ipv4_cidr" {
  type    = string
  default = "172.16.0.0/28"
}
variable "kubernetes" {
  type = object({
    version   = string
    node_min  = number
    node_max  = number
    node_size = string
  })
}
variable "labels" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"

  machine_types = {
    small   = "e2-standard-2"
    medium  = "e2-standard-4"
    large   = "e2-standard-8"
    xlarge  = "e2-standard-16"
  }
  machine_type = lookup(local.machine_types, var.kubernetes.node_size, var.kubernetes.node_size)
}

resource "google_container_cluster" "this" {
  project    = var.gcp_project_id
  name       = "${local.prefix}-gke"
  location   = var.region
  network    = var.network_id
  subnetwork = var.subnet_id

  remove_default_node_pool = true
  initial_node_count       = 1
  min_master_version       = var.kubernetes.version
  deletion_protection      = false

  release_channel {
    channel = "REGULAR"
  }

  workload_identity_config {
    workload_pool = "${var.gcp_project_id}.svc.id.goog"
  }

  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = var.master_ipv4_cidr
  }

  resource_labels = var.labels
}

resource "google_service_account" "nodes" {
  project      = var.gcp_project_id
  account_id   = "${local.prefix}-gke-node"
  display_name = "GKE node SA for ${local.prefix}"
}

resource "google_container_node_pool" "primary" {
  project    = var.gcp_project_id
  name       = "${local.prefix}-pool"
  location   = var.region
  cluster    = google_container_cluster.this.name
  node_count = var.kubernetes.node_min

  autoscaling {
    min_node_count = var.kubernetes.node_min
    max_node_count = var.kubernetes.node_max
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }

  node_config {
    machine_type    = local.machine_type
    service_account = google_service_account.nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]
    labels          = var.labels

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }
  }
}

output "cluster_name" { value = google_container_cluster.this.name }
output "cluster_endpoint" {
  value     = google_container_cluster.this.endpoint
  sensitive = true
}
output "cluster_ca_certificate" {
  value     = google_container_cluster.this.master_auth[0].cluster_ca_certificate
  sensitive = true
}
output "node_service_account" { value = google_service_account.nodes.email }
