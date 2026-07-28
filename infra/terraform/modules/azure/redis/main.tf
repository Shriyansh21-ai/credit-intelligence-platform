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

variable "redis" {
  type = object({
    node_size = string
    num_nodes = number
  })
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  prefix = "${var.project}-${var.environment}"

  redis_sku_map = {
    "Standard_C0" = { family = "C", sku_name = "Standard", capacity = 0 }
    "Standard_C1" = { family = "C", sku_name = "Standard", capacity = 1 }
    "Standard_C2" = { family = "C", sku_name = "Standard", capacity = 2 }
    "Standard_C3" = { family = "C", sku_name = "Standard", capacity = 3 }
    "Standard_P1" = { family = "P", sku_name = "Premium", capacity = 1 }
    "Standard_P2" = { family = "P", sku_name = "Premium", capacity = 2 }
    "Standard_P3" = { family = "P", sku_name = "Premium", capacity = 3 }
  }

  redis_sel = lookup(
    local.redis_sku_map,
    var.redis.node_size,
    { family = "C", sku_name = "Standard", capacity = 1 }
  )

  is_premium = local.redis_sel.sku_name == "Premium"
}

resource "azurerm_redis_cache" "this" {
  name                = "${local.prefix}-redis"
  location            = var.region
  resource_group_name = var.resource_group_name
  capacity            = local.redis_sel.capacity
  family              = local.redis_sel.family
  sku_name            = local.redis_sel.sku_name
  minimum_tls_version = "1.2"
  enable_non_ssl_port = false

  shard_count = local.is_premium && var.redis.num_nodes > 1 ? var.redis.num_nodes : null

  redis_configuration {
    maxmemory_policy = "allkeys-lru"
  }

  tags = var.tags
}

output "redis_endpoint" {
  value     = "${azurerm_redis_cache.this.hostname}:${azurerm_redis_cache.this.ssl_port}"
  sensitive = true
}

output "redis_name" {
  value = azurerm_redis_cache.this.name
}

output "redis_primary_access_key" {
  value     = azurerm_redis_cache.this.primary_access_key
  sensitive = true
}
