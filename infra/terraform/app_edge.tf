locals {
  app_edge_enabled               = var.enable_app_hosting && var.enable_app_edge
  app_domain_name_trimmed        = trimspace(var.app_domain_name)
  app_load_balancer_name         = "${var.app_service_name}-app-lb"
  app_security_policy_name       = "${var.app_service_name}-armor"
  app_backend_service_name       = "${var.app_service_name}-backend"
  app_serverless_neg_name        = "${var.app_service_name}-neg"
  app_https_proxy_name           = "${var.app_service_name}-https-proxy"
  app_http_proxy_name            = "${var.app_service_name}-http-proxy"
  app_https_url_map_name         = "${var.app_service_name}-https-map"
  app_http_redirect_url_map_name = "${var.app_service_name}-http-redirect"
  app_https_forwarding_rule_name = "${var.app_service_name}-https-fr"
  app_http_forwarding_rule_name  = "${var.app_service_name}-http-fr"
  app_certificate_name           = "${var.app_service_name}-cert"
  app_global_address_name        = "${var.app_service_name}-ip"
}

resource "google_compute_global_address" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project      = var.project_id
  name         = local.app_global_address_name
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

resource "google_compute_managed_ssl_certificate" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project = var.project_id
  name    = local.app_certificate_name

  managed {
    domains = [local.app_domain_name_trimmed]
  }
}

resource "google_compute_region_network_endpoint_group" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project               = var.project_id
  region                = local.automation_region
  name                  = local.app_serverless_neg_name
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.app[0].name
  }
}

resource "google_compute_security_policy" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project     = var.project_id
  name        = local.app_security_policy_name
  description = "Public edge policy for the TidingsIQ Streamlit app."

  rule {
    priority    = 1000
    action      = "throttle"
    description = "Preview-first per-IP throttle for normal browsing bursts."
    preview     = var.app_rate_limit_preview

    match {
      versioned_expr = "SRC_IPS_V1"

      config {
        src_ip_ranges = ["*"]
      }
    }

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"
      enforce_on_key = "IP"

      rate_limit_threshold {
        count        = var.app_rate_limit_count
        interval_sec = var.app_rate_limit_interval_sec
      }
    }
  }

  rule {
    priority    = 2147483647
    action      = "allow"
    description = "Default allow rule for public TidingsIQ app traffic."

    match {
      versioned_expr = "SRC_IPS_V1"

      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}

resource "google_compute_backend_service" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project               = var.project_id
  name                  = local.app_backend_service_name
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  security_policy       = google_compute_security_policy.app[0].id

  backend {
    group = google_compute_region_network_endpoint_group.app[0].id
  }

  log_config {
    enable      = true
    sample_rate = var.app_backend_log_sample_rate
  }
}

resource "google_compute_url_map" "app_https" {
  count = local.app_edge_enabled ? 1 : 0

  project         = var.project_id
  name            = local.app_https_url_map_name
  default_service = google_compute_backend_service.app[0].id
}

resource "google_compute_target_https_proxy" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project          = var.project_id
  name             = local.app_https_proxy_name
  url_map          = google_compute_url_map.app_https[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.app[0].id]
}

resource "google_compute_global_forwarding_rule" "app_https" {
  count = local.app_edge_enabled ? 1 : 0

  project               = var.project_id
  name                  = local.app_https_forwarding_rule_name
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.app[0].id
  ip_address            = google_compute_global_address.app[0].id
}

resource "google_compute_url_map" "app_http_redirect" {
  count = local.app_edge_enabled ? 1 : 0

  project = var.project_id
  name    = local.app_http_redirect_url_map_name

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_target_http_proxy" "app" {
  count = local.app_edge_enabled ? 1 : 0

  project = var.project_id
  name    = local.app_http_proxy_name
  url_map = google_compute_url_map.app_http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "app_http" {
  count = local.app_edge_enabled ? 1 : 0

  project               = var.project_id
  name                  = local.app_http_forwarding_rule_name
  load_balancing_scheme = "EXTERNAL_MANAGED"
  ip_protocol           = "TCP"
  port_range            = "80"
  target                = google_compute_target_http_proxy.app[0].id
  ip_address            = google_compute_global_address.app[0].id
}

resource "google_logging_metric" "app_lb_request_count" {
  count = local.app_edge_enabled ? 1 : 0

  project     = var.project_id
  name        = "app_lb_request_count"
  description = "Count of load-balanced requests served by the TidingsIQ app backend."
  filter      = <<-EOT
resource.type="http_load_balancer"
resource.labels.backend_service_name="${local.app_backend_service_name}"
EOT
}

resource "google_logging_metric" "app_lb_throttle_preview_exceeds" {
  count = local.app_edge_enabled ? 1 : 0

  project     = var.project_id
  name        = "app_lb_throttle_preview_exceeds"
  description = "Count of Cloud Armor preview-mode throttle threshold exceeds for the TidingsIQ app."
  filter      = <<-EOT
resource.type="http_load_balancer"
resource.labels.backend_service_name="${local.app_backend_service_name}"
jsonPayload.previewSecurityPolicy.configuredAction="THROTTLE"
jsonPayload.previewSecurityPolicy.rateLimitAction.outcome="RATE_LIMIT_THRESHOLD_EXCEED"
EOT
}

resource "google_logging_metric" "app_lb_throttle_denied" {
  count = local.app_edge_enabled ? 1 : 0

  project     = var.project_id
  name        = "app_lb_throttle_denied"
  description = "Count of Cloud Armor enforced throttle denials for the TidingsIQ app."
  filter      = <<-EOT
resource.type="http_load_balancer"
resource.labels.backend_service_name="${local.app_backend_service_name}"
jsonPayload.enforcedSecurityPolicy.configuredAction="THROTTLE"
jsonPayload.statusDetails="denied_by_security_policy"
EOT
}

resource "google_logging_metric" "app_bigquery_query_jobs" {
  count = local.app_edge_enabled ? 1 : 0

  project     = var.project_id
  name        = "app_bigquery_query_jobs"
  description = "Count of BigQuery jobs submitted by the TidingsIQ app service account."
  filter      = <<-EOT
resource.type="bigquery_project"
protoPayload.serviceName="bigquery.googleapis.com"
protoPayload.methodName="jobservice.insert"
protoPayload.authenticationInfo.principalEmail="${google_service_account.app[0].email}"
EOT
}

resource "google_monitoring_dashboard" "app_edge" {
  count = local.app_edge_enabled ? 1 : 0

  dashboard_json = jsonencode({
    displayName = "TidingsIQ App Edge"
    mosaicLayout = {
      columns = 12
      tiles = [
        {
          xPos   = 0
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "LB Request Volume"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "App backend requests"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.app_lb_request_count[0].name}\" resource.type=\"l7_lb_rule\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 0
          width  = 6
          height = 4
          widget = {
            title = "Cloud Armor Throttle Signals"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Preview exceeds"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.app_lb_throttle_preview_exceeds[0].name}\" resource.type=\"l7_lb_rule\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_SUM"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
                {
                  plotType       = "LINE"
                  legendTemplate = "Enforced denies"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.app_lb_throttle_denied[0].name}\" resource.type=\"l7_lb_rule\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_SUM"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "count"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 4
          width  = 4
          height = 4
          widget = {
            title = "Cloud Run Request Count"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Requests"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.app_service_name}\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_RATE"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "req/s"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 4
          width  = 4
          height = 4
          widget = {
            title = "Cloud Run Active Instances"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Active instances"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.app_service_name}\" metric.labels.state=\"active\""
                      aggregation = {
                        alignmentPeriod    = "60s"
                        perSeriesAligner   = "ALIGN_MAX"
                        crossSeriesReducer = "REDUCE_MAX"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "instances"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 4
          width  = 4
          height = 4
          widget = {
            title = "Cloud Run P95 Latency"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "P95 latency"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.app_service_name}\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_95"
                        crossSeriesReducer = "REDUCE_MAX"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "ms"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "Cloud Run CPU And Memory"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "CPU p95"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/container/cpu/utilizations\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.app_service_name}\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_95"
                        crossSeriesReducer = "REDUCE_MEAN"
                        groupByFields      = []
                      }
                    }
                  }
                },
                {
                  plotType       = "LINE"
                  legendTemplate = "Memory p95"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"run.googleapis.com/container/memory/utilizations\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.app_service_name}\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_PERCENTILE_95"
                        crossSeriesReducer = "REDUCE_MEAN"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "utilization"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 6
          yPos   = 8
          width  = 6
          height = 4
          widget = {
            title = "App-attributed BigQuery Query Jobs"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "App query jobs"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.app_bigquery_query_jobs[0].name}\" resource.type=\"bigquery_project\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_SUM"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "jobs"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 0
          yPos   = 12
          width  = 4
          height = 4
          widget = {
            title = "BigQuery Query Count"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Queries in flight"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"bigquery.googleapis.com/query/count\" resource.type=\"global\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_MAX"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "queries"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 4
          yPos   = 12
          width  = 4
          height = 4
          widget = {
            title = "BigQuery Query Executions"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Executed queries"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"bigquery.googleapis.com/query/execution_count\" resource.type=\"bigquery_project\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_SUM"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "queries"
                scale = "LINEAR"
              }
            }
          }
        },
        {
          xPos   = 8
          yPos   = 12
          width  = 4
          height = 4
          widget = {
            title = "BigQuery Scanned Bytes Billed"
            xyChart = {
              dataSets = [
                {
                  plotType       = "LINE"
                  legendTemplate = "Billed bytes"
                  timeSeriesQuery = {
                    timeSeriesFilter = {
                      filter = "metric.type=\"bigquery.googleapis.com/query/scanned_bytes_billed\" resource.type=\"global\""
                      aggregation = {
                        alignmentPeriod    = "300s"
                        perSeriesAligner   = "ALIGN_SUM"
                        crossSeriesReducer = "REDUCE_SUM"
                        groupByFields      = []
                      }
                    }
                  }
                },
              ]
              timeshiftDuration = "0s"
              yAxis = {
                label = "bytes"
                scale = "LINEAR"
              }
            }
          }
        },
      ]
    }
  })
}

resource "google_monitoring_alert_policy" "app_cloud_run_instance_pressure" {
  count = local.app_edge_enabled ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ App Cloud Run Instance Pressure"
  combiner              = "OR"
  enabled               = true
  notification_channels = local.enable_notification_email ? [google_monitoring_notification_channel.pipeline_email[0].name] : []

  conditions {
    display_name = "Cloud Run active instances stayed near the configured cap for 5 minutes"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${var.app_service_name}\" AND metric.type=\"run.googleapis.com/container/instance_count\" AND metric.labels.state=\"active\""
      comparison      = "COMPARISON_GT"
      threshold_value = max(var.app_max_instance_count - 0.5, 0.5)
      duration        = "300s"

      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = []
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "1800s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "The TidingsIQ app reached or stayed near its configured Cloud Run `app_max_instance_count` for at least five minutes. Check request volume, Cloud Armor throttle signals, and request latencies before raising the cap."
  }
}
