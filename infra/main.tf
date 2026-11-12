resource "azurerm_resource_group" "main" {
  name     = var.names.resource_group
  location = local.location
}
