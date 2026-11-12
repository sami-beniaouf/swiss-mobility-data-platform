locals {
  location = "switzerlandnorth"
  rg_id    = "/subscriptions/${var.subscription_id}/resourceGroups/rg-swiss_mobility"
}

data "azurerm_client_config" "current" {}
