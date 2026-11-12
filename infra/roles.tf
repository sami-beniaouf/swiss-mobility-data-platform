# Some assignments were created with a lower-case "resourcegroups" in their scope.
# Azure treats both spellings as the same resource, Terraform does not: the scope is
# written exactly as stored, otherwise Terraform would delete and recreate the assignment.
locals {
  lake_scope_lc     = replace(azurerm_storage_account.lake.id, "/resourceGroups/", "/resourcegroups/")
  function_scope_lc = replace(azurerm_function_app_flex_consumption.ingestion.id, "/resourceGroups/", "/resourcegroups/")
}

# Permissions the platform needs to run. Personal administration access (Reader,
# Key Vault Secrets Officer for people) is granted outside this configuration.

# Function managed identity: writes bronze files, reads the Oracle secrets.
resource "azurerm_role_assignment" "function_lake" {
  scope                = local.lake_scope_lc
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_function_app_flex_consumption.ingestion.identity[0].principal_id
}

resource "azurerm_role_assignment" "function_secrets" {
  scope                = azurerm_key_vault.main.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_function_app_flex_consumption.ingestion.identity[0].principal_id
}

# Local runs of the ingestion (docker compose): same write access as the Function.
resource "azurerm_role_assignment" "local_lake" {
  scope                = azurerm_storage_account.lake.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = var.local_sp_object_id
}

# GitHub Actions deploys the code of this Function App only.
resource "azurerm_role_assignment" "github_deploy" {
  scope                = local.function_scope_lc
  role_definition_name = "Website Contributor"
  principal_id         = var.github_sp_object_id
}

# The OneLake shortcut reads bronze files, nothing else.
resource "azurerm_role_assignment" "fabric_shortcut" {
  scope                = local.lake_scope_lc
  role_definition_name = "Storage Blob Data Reader"
  principal_id         = var.fabric_shortcut_object_id
}
