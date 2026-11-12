# Data lake: bronze Parquet files written by the Function, read by Fabric through a
# OneLake shortcut; "state" holds the station cache.
resource "azurerm_storage_account" "lake" {
  name                            = "stswissmobility"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = local.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  access_tier                     = "Hot"
  is_hns_enabled                  = true # ADLS Gen2
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false

  blob_properties {
    delete_retention_policy {
      days = 7
    }
    container_delete_retention_policy {
      days = 7
    }
  }
}

resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_id    = azurerm_storage_account.lake.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "state" {
  name                  = "state"
  storage_account_id    = azurerm_storage_account.lake.id
  container_access_type = "private"
}

# Internal storage of the Function App: deployment packages and runtime files.
resource "azurerm_storage_account" "function" {
  name                            = "rgswissmobility9ce9"
  resource_group_name             = azurerm_resource_group.main.name
  location                        = local.location
  account_kind                    = "StorageV2"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  access_tier                     = "Hot"
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  default_to_oauth_authentication = true
}
