# Terraform state in Azure Storage. The storage account is created once by hand
# (see the bootstrap commands in infra/README.md): it cannot be managed by the
# configuration whose state it stores.
terraform {
  backend "azurerm" {
    resource_group_name  = "rg-swiss_mobility"
    storage_account_name = "stswissmobilitytfstate"
    container_name       = "tfstate"
    key                  = "swiss-mobility.tfstate"
  }
}
