# Terraform state in Azure Storage. A backend block cannot use variables: the
# location of the state is passed at init time, see backend.hcl.
#   terraform init -backend-config=backend.hcl
# The storage account is created once by hand (bootstrap commands in infra/README.md):
# it cannot be managed by the configuration whose state it stores.
terraform {
  backend "azurerm" {
    key = "swiss-mobility.tfstate"
  }
}
