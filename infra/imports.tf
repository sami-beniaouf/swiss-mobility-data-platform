# Resources created before Terraform was introduced: adopted into the state, not recreated.

import {
  to = azurerm_resource_group.main
  id = local.rg_id
}

import {
  to = azurerm_storage_account.lake
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility"
}

import {
  to = azurerm_storage_container.bronze
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility/blobServices/default/containers/bronze"
}

import {
  to = azurerm_storage_container.state
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility/blobServices/default/containers/state"
}

import {
  to = azurerm_storage_account.function
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/rgswissmobility9ce9"
}

import {
  to = azurerm_key_vault.main
  id = "${local.rg_id}/providers/Microsoft.KeyVault/vaults/kv-swissmobility-sb"
}

import {
  to = azurerm_service_plan.function
  id = "${local.rg_id}/providers/Microsoft.Web/serverFarms/ASP-rgswissmobility-ae23"
}

import {
  to = azurerm_function_app_flex_consumption.ingestion
  id = "${local.rg_id}/providers/Microsoft.Web/sites/func-swissmobility-sb"
}

import {
  to = azurerm_application_insights.function
  id = "${local.rg_id}/providers/Microsoft.Insights/components/func-swissmobility-sb"
}

import {
  to = azurerm_monitor_action_group.oncall
  id = "${local.rg_id}/providers/Microsoft.Insights/actionGroups/ag-swissmobility-oncall"
}

import {
  to = azurerm_monitor_scheduled_query_rules_alert_v2.run_failed
  id = "${local.rg_id}/providers/Microsoft.Insights/scheduledQueryRules/alert-ingestion-run-failed"
}

import {
  to = azurerm_monitor_scheduled_query_rules_alert_v2.heartbeat
  id = "${local.rg_id}/providers/Microsoft.Insights/scheduledQueryRules/alert-ingestion-heartbeat"
}
