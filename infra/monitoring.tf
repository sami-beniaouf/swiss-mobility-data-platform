# Azure stores the scope of the alert rules with a lower-case provider namespace;
# the same string is used here so that Terraform does not see a difference.
locals {
  app_insights_scope = replace(azurerm_application_insights.function.id, "Microsoft.Insights", "microsoft.insights")
}

# Log Analytics workspace created by Azure for the region: used, not managed here.
data "azurerm_log_analytics_workspace" "default" {
  name                = "DefaultWorkspace-${var.subscription_id}-CHN"
  resource_group_name = "DefaultResourceGroup-CHN"
}

resource "azurerm_application_insights" "function" {
  name                = "func-swissmobility-sb"
  resource_group_name = azurerm_resource_group.main.name
  location            = local.location
  application_type    = "web"
  workspace_id        = data.azurerm_log_analytics_workspace.default.id
  retention_in_days   = 90
  sampling_percentage = 0
}

resource "azurerm_monitor_action_group" "oncall" {
  name                = "ag-swissmobility-oncall"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "sm-oncall"

  email_receiver {
    name          = "email-sami_-EmailAction-"
    email_address = var.alert_email
  }
}

# A run ended with an error.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "run_failed" {
  name                    = "alert-ingestion-run-failed"
  display_name            = "alert-ingestion-run-failed"
  description             = "An ingestion run failed (more than 50 % of stations, storage or station list). See the run log in Application Insights."
  resource_group_name     = azurerm_resource_group.main.name
  location                = local.location
  scopes                  = [local.app_insights_scope]
  target_resource_types   = ["microsoft.insights/components"]
  severity                = 1
  auto_mitigation_enabled = true # resolves the alert once a run succeeds
  evaluation_frequency    = "PT15M"
  window_duration         = "PT15M"

  criteria {
    query                   = <<-KQL
      requests
      | where name in ("ingest_stationboard", "export_reference")
      | where success == false
    KQL
    time_aggregation_method = "Count"
    operator                = "GreaterThan"
    threshold               = 0

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.oncall.id]
  }
}

# No successful departures run for three cycles: the Function is stopped, not
# loading, or its timer does not fire.
resource "azurerm_monitor_scheduled_query_rules_alert_v2" "heartbeat" {
  name                    = "alert-ingestion-heartbeat"
  display_name            = "alert-ingestion-heartbeat"
  description             = "No successful ingestion run in the last 45 minutes. The Function may be stopped, failing to load, or not triggered."
  resource_group_name     = azurerm_resource_group.main.name
  location                = local.location
  scopes                  = [local.app_insights_scope]
  target_resource_types   = ["microsoft.insights/components"]
  severity                = 1
  auto_mitigation_enabled = true # resolves the alert once a run succeeds
  evaluation_frequency    = "PT15M"
  window_duration         = "PT45M"

  criteria {
    query                   = <<-KQL
      requests
      | where name == "ingest_stationboard"
      | where success == true
    KQL
    time_aggregation_method = "Count"
    operator                = "LessThan"
    threshold               = 1

    failing_periods {
      minimum_failing_periods_to_trigger_alert = 1
      number_of_evaluation_periods             = 1
    }
  }

  action {
    action_groups = [azurerm_monitor_action_group.oncall.id]
  }
}
