variable "subscription_id" {
  description = "Azure subscription that holds the platform"
  type        = string
}

variable "location" {
  description = "Azure region of every resource"
  type        = string
  default     = "switzerlandnorth"
}

variable "names" {
  description = "Resource names. Storage account and Key Vault names are unique across Azure."
  type = object({
    resource_group           = string
    lake_storage             = string # 3-24 lower-case letters and digits
    function_storage         = string
    function_package         = string # blob container holding the deployed code
    key_vault                = string
    service_plan             = string
    function_app             = string # also the name of Application Insights
    action_group             = string
  })
}

variable "log_analytics_workspace_id" {
  description = "Existing Log Analytics workspace for Application Insights; null creates one"
  type        = string
  default     = null
}

variable "alert_email" {
  description = "Address notified by the action group"
  type        = string
  sensitive   = true
}

variable "oracle_cloud_dsn" {
  description = "Connect descriptor of the Oracle Autonomous Database (host and service name)"
  type        = string
  sensitive   = true
}

variable "local_sp_object_id" {
  description = "Object ID of sp-swissmobility-local (ingestion run from the developer machine)"
  type        = string
}

variable "github_sp_object_id" {
  description = "Object ID of sp-swissmobility-github (deployment of the Function code from GitHub Actions)"
  type        = string
}

variable "fabric_shortcut_object_id" {
  description = "Object ID of the account used by the OneLake shortcut to read the bronze container"
  type        = string
}
