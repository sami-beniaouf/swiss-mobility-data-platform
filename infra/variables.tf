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
