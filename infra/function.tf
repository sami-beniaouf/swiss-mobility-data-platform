resource "azurerm_service_plan" "function" {
  name                = "ASP-rgswissmobility-ae23"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  os_type             = "Linux"
  sku_name            = "FC1" # Flex Consumption
}

# Ingestion: timer triggers every 15 minutes (departures) and daily (reference data).
# The code is deployed by GitHub Actions, not by Terraform.
resource "azurerm_function_app_flex_consumption" "ingestion" {
  name                = "func-swissmobility-sb"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  service_plan_id     = azurerm_service_plan.function.id

  runtime_name           = "python"
  runtime_version        = "3.13"
  instance_memory_in_mb  = 512
  maximum_instance_count = 100
  https_only             = true

  storage_container_type      = "blobContainer"
  storage_container_endpoint  = "${azurerm_storage_account.function.primary_blob_endpoint}app-package-func-swissmobility-sb-3597edc"
  storage_authentication_type = "StorageAccountConnectionString"
  storage_access_key          = azurerm_storage_account.function.primary_access_key

  identity {
    type = "SystemAssigned"
  }

  app_settings = {
    ORACLE_TARGET          = "cloud"
    STORAGE_TARGET         = "adls"
    ADLS_ACCOUNT_NAME      = azurerm_storage_account.lake.name
    ORACLE_CLOUD_USER      = "mobility"
    ORACLE_CLOUD_DSN       = var.oracle_cloud_dsn
    ORACLE_CLOUD_PASSWORD  = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=oracle-cloud-password)"
    ORACLE_WALLET_PASSWORD = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=oracle-wallet-password)"
    ORACLE_WALLET_PEM_B64  = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=oracle-wallet-pem-b64)"

    "AzureWebJobs.ingest_stationboard.Disabled" = "0"
  }

  site_config {
    application_insights_connection_string = azurerm_application_insights.function.connection_string

    cors {
      allowed_origins = ["https://portal.azure.com"]
    }
  }

  tags = {
    "hidden-link: /app-insights-resource-id" = "${local.rg_id}/providers/microsoft.insights/components/func-swissmobility-sb"
  }
}
