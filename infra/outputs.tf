output "function_app_hostname" {
  description = "Default host name of the Function App"
  value       = azurerm_function_app_flex_consumption.ingestion.default_hostname
}

output "function_principal_id" {
  description = "Object ID of the Function managed identity"
  value       = azurerm_function_app_flex_consumption.ingestion.identity[0].principal_id
}

output "lake_dfs_endpoint" {
  description = "ADLS Gen2 endpoint of the data lake, used by the OneLake shortcut"
  value       = azurerm_storage_account.lake.primary_dfs_endpoint
}

output "key_vault_uri" {
  description = "URI of the Key Vault holding the Oracle secrets"
  value       = azurerm_key_vault.main.vault_uri
}
