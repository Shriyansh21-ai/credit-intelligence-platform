variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "region" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "aks_subnet_id" {
  type = string
}

variable "kubernetes" {
  type = object({
    version   = string
    node_min  = number
    node_max  = number
    node_size = string
  })
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"
}

resource "azurerm_kubernetes_cluster" "this" {
  name                = "${local.prefix}-aks"
  location            = var.region
  resource_group_name = var.resource_group_name
  dns_prefix          = local.prefix
  kubernetes_version  = var.kubernetes.version

  role_based_access_control_enabled = true
  oidc_issuer_enabled               = true
  workload_identity_enabled         = true

  default_node_pool {
    name                 = "system"
    vm_size              = var.kubernetes.node_size
    vnet_subnet_id       = var.aks_subnet_id
    orchestrator_version = var.kubernetes.version
    enable_auto_scaling  = true
    min_count            = 1
    max_count            = 3
    node_labels = {
      "pool" = "system"
    }
  }

  identity {
    type = "SystemAssigned"
  }

  azure_active_directory_role_based_access_control {
    managed            = true
    azure_rbac_enabled = true
  }

  network_profile {
    network_plugin    = "azure"
    network_policy    = "azure"
    load_balancer_sku = "standard"
    outbound_type     = "userAssignedNATGateway"
    service_cidr      = "10.30.0.0/16"
    dns_service_ip    = "10.30.0.10"
  }

  tags = var.tags
}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "user"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.this.id
  vm_size               = var.kubernetes.node_size
  vnet_subnet_id        = var.aks_subnet_id
  orchestrator_version  = var.kubernetes.version
  mode                  = "User"
  enable_auto_scaling   = true
  min_count             = var.kubernetes.node_min
  max_count             = var.kubernetes.node_max

  node_labels = {
    "pool" = "user"
  }

  tags = var.tags
}

output "cluster_name" {
  value = azurerm_kubernetes_cluster.this.name
}

output "cluster_id" {
  value = azurerm_kubernetes_cluster.this.id
}

output "cluster_endpoint" {
  value     = azurerm_kubernetes_cluster.this.kube_config.0.host
  sensitive = true
}

output "oidc_issuer_url" {
  value = azurerm_kubernetes_cluster.this.oidc_issuer_url
}

output "kubelet_identity_object_id" {
  value = azurerm_kubernetes_cluster.this.kubelet_identity.0.object_id
}
