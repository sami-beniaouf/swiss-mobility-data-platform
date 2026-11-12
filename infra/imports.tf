# Role assignments created before Terraform was introduced: adopted into the state.
# This file is removed once the import has been applied.

import {
  to = azurerm_role_assignment.function_lake
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility/providers/Microsoft.Authorization/roleAssignments/69a232b2-724a-4094-bcfb-c51db373c094"
}

import {
  to = azurerm_role_assignment.function_secrets
  id = "${local.rg_id}/providers/Microsoft.KeyVault/vaults/kv-swissmobility-sb/providers/Microsoft.Authorization/roleAssignments/ac934f79-d51f-40dc-ba7b-2ec4b381185a"
}

import {
  to = azurerm_role_assignment.local_lake
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility/providers/Microsoft.Authorization/roleAssignments/20b70fea-5ea6-4fcb-b9b8-ae43bbeddce2"
}

import {
  to = azurerm_role_assignment.github_deploy
  id = "${local.rg_id}/providers/Microsoft.Web/sites/func-swissmobility-sb/providers/Microsoft.Authorization/roleAssignments/70455ce8-af4e-45aa-be2d-8eeccd263168"
}

import {
  to = azurerm_role_assignment.fabric_shortcut
  id = "${local.rg_id}/providers/Microsoft.Storage/storageAccounts/stswissmobility/providers/Microsoft.Authorization/roleAssignments/9d9656dd-71bc-4ed8-9b71-89909d9cccfb"
}
