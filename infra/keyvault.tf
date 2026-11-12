# Oracle credentials. Secret values are not managed by Terraform: they would be
# written to the state. They are set once with "az keyvault secret set".
resource "azurerm_key_vault" "main" {
  name                       = var.names.key_vault
  resource_group_name        = azurerm_resource_group.main.name
  location                   = local.location
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  rbac_authorization_enabled = true
  soft_delete_retention_days = 90
  purge_protection_enabled   = false
}
