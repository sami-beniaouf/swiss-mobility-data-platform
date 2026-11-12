resource "azurerm_resource_group" "main" {
  name     = "rg-swiss_mobility"
  location = local.location
}
