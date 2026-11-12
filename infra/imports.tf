# Deployment container of the Function, created by Azure with the Function App:
# adopted into the state. This file is removed once the import has been applied.
import {
  to = azurerm_storage_container.function_package
  id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.names.resource_group}/providers/Microsoft.Storage/storageAccounts/${var.names.function_storage}/blobServices/default/containers/${var.names.function_package}"
}
