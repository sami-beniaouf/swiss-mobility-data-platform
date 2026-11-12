variable "subscription_id" {
  description = "Azure subscription that holds the platform"
  type        = string
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
