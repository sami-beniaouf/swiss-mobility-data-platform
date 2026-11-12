# Azure infrastructure (Terraform)

The Azure part of the platform is described here: resource group, data lake and
containers, Key Vault, Function App and its plan and storage, Application Insights,
action group, alert rules and the role assignments the platform needs.

Not managed here, on purpose:

| What | Where |
|---|---|
| Function code | deployed by GitHub Actions (`.github/workflows/ci.yml`) |
| Secret values (Oracle password, wallet) | set with `az keyvault secret set`: a value managed by Terraform would be stored in the state |
| Fabric items (Lakehouse, notebook, Warehouse, report) | Fabric Git integration, `fabric/workspace/` |
| App registrations (`sp-swissmobility-*`) | Entra ID; their object IDs are inputs |
| Personal access of administrators | granted per person |

The resources were first created by hand and then adopted with `import` blocks;
`terraform plan` reports no changes against the deployed platform.

## Files

| File | Content |
|---|---|
| `main.tf` | resource group |
| `storage.tf` | data lake (`bronze`, `state`), Function storage and deployment container |
| `keyvault.tf` | Key Vault (RBAC authorization) |
| `function.tf` | Flex Consumption plan and Function App, app settings with Key Vault references |
| `monitoring.tf` | Log Analytics (existing or new), Application Insights, action group, alert rules |
| `roles.tf` | role assignments of the Function identity and of the service principals |
| `variables.tf`, `terraform.tfvars.example` | inputs: names, subscription, e-mail, Oracle connect descriptor, object IDs |
| `backend.tf`, `backend.hcl` | remote state in Azure Storage |
| `outputs.tf` | host name, identity, lake endpoint, Key Vault URI |

## State

The state is stored in the blob container `tfstate` of the storage account
`stswissmobilitytfstate` (versioning enabled). This account is created once, outside
Terraform:

```bash
az storage account create -n stswissmobilitytfstate -g rg-swiss_mobility -l switzerlandnorth \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 --allow-blob-public-access false
az storage account blob-service-properties update -n stswissmobilitytfstate -g rg-swiss_mobility --enable-versioning true
az storage container create -n tfstate --account-name stswissmobilitytfstate
```

## Usage

From a shell signed in to Azure (`az login`; Azure Cloud Shell has Terraform installed):

```bash
cp terraform.tfvars.example terraform.tfvars   # then fill in the values
terraform init -backend-config=backend.hcl
terraform plan -out=changes.tfplan
terraform apply changes.tfplan
```

`terraform.tfvars` holds the subscription ID, the alert e-mail address and the Oracle
connect descriptor; it is git-ignored.

## Making a change

Every change goes through the code; the portal is used to look, not to change.

1. Edit the `.tf` files: add a block to create a resource, change a value to update it,
   remove a block to delete it.
2. `terraform plan -out=changes.tfplan` and read the plan. Terraform reads the deployed
   resources first, then compares them with the code and the state. `-/+` means the
   resource is deleted and recreated: often caused by a value that cannot change in
   place, sometimes by a difference that Azure ignores (upper and lower case in an
   ID). It is resolved in the code before applying.
3. `terraform apply changes.tfplan` applies exactly the plan that was read.

A change made in the portal shows up in the next plan as a difference with the code
(drift); it is either written into the code or reverted by the next apply.

`terraform destroy` deletes every resource recorded in the state. It is meant for
test environments only (see below).

## New environment

The same configuration creates the platform in another subscription:

1. create the state storage (above) and adapt `backend.hcl`, or use another `key` so
   that the environment gets its own state;
2. choose new names in `terraform.tfvars` (storage account and Key Vault names are
   unique across Azure) and leave out `log_analytics_workspace_id` to create a workspace;
3. `terraform apply`;
4. set the three Oracle secrets in the Key Vault;
5. deploy the Function code from GitHub Actions.

A test environment created this way is removed with `terraform destroy`, which deletes
only the resources of its own state.
