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

variable "delegated_subnet_id" {
  type = string
}

variable "virtual_network_id" {
  type = string
}

variable "database" {
  type = object({
    engine_version    = string
    instance_size     = string
    storage_gb        = number
    high_availability = bool
  })
}

variable "administrator_login" {
  type    = string
  default = "pgadmin"
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  prefix        = "${var.project}-${var.environment}"
  database_name = replace("${var.project}_${var.environment}", "-", "_")
}

resource "random_password" "admin" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]"
}

resource "azurerm_private_dns_zone" "pg" {
  name                = "${replace(local.prefix, "-", "")}.private.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "pg" {
  name                  = "${local.prefix}-pg-link"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.pg.name
  virtual_network_id    = var.virtual_network_id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_postgresql_flexible_server" "this" {
  name                          = "${local.prefix}-pg"
  resource_group_name           = var.resource_group_name
  location                      = var.region
  version                       = var.database.engine_version
  sku_name                      = var.database.instance_size
  storage_mb                    = var.database.storage_gb * 1024
  delegated_subnet_id           = var.delegated_subnet_id
  private_dns_zone_id           = azurerm_private_dns_zone.pg.id
  administrator_login           = var.administrator_login
  administrator_password        = random_password.admin.result
  zone                          = "1"
  public_network_access_enabled = false
  backup_retention_days         = 7

  dynamic "high_availability" {
    for_each = var.database.high_availability ? [1] : []
    content {
      mode                      = "ZoneRedundant"
      standby_availability_zone = "2"
    }
  }

  tags = var.tags

  depends_on = [azurerm_private_dns_zone_virtual_network_link.pg]
}

resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = local.database_name
  server_id = azurerm_postgresql_flexible_server.this.id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

output "database_endpoint" {
  value     = azurerm_postgresql_flexible_server.this.fqdn
  sensitive = true
}

output "database_name" {
  value = azurerm_postgresql_flexible_server_database.this.name
}

output "administrator_login" {
  value = var.administrator_login
}

output "administrator_password" {
  value     = random_password.admin.result
  sensitive = true
}
