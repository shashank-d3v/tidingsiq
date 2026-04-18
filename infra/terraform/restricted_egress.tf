locals {
  enable_restricted_egress_resources = var.enable_restricted_egress && (
    var.enable_pipeline_automation
    || var.enable_bronze_archive_automation
  )
  restricted_egress_name_prefix          = "tidingsiq-restricted-egress-${var.environment}"
  restricted_egress_network_name         = local.restricted_egress_name_prefix
  restricted_egress_subnet_name          = "${local.restricted_egress_name_prefix}-subnet"
  restricted_egress_router_name          = "${local.restricted_egress_name_prefix}-router"
  restricted_egress_nat_name             = "${local.restricted_egress_name_prefix}-nat"
  restricted_egress_connector_name       = "tiq-eg-${var.environment}"
  restricted_egress_metadata_rule_name   = "${local.restricted_egress_name_prefix}-metadata-deny"
  restricted_egress_non_public_rule_name = "${local.restricted_egress_name_prefix}-non-public-deny"
  restricted_egress_non_public_ranges = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "100.64.0.0/10",
  ]
}

resource "google_compute_network" "restricted_egress" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project                 = var.project_id
  name                    = local.restricted_egress_network_name
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"
  description             = "Dedicated VPC for restricted outbound traffic from TidingsIQ serverless workloads."
}

resource "google_compute_subnetwork" "restricted_egress" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project                  = var.project_id
  name                     = local.restricted_egress_subnet_name
  region                   = local.automation_region
  ip_cidr_range            = var.restricted_egress_subnet_cidr
  network                  = google_compute_network.restricted_egress[0].id
  private_ip_google_access = true
  description              = "Dedicated subnet for TidingsIQ restricted-egress serverless networking."
}

resource "google_vpc_access_connector" "restricted_egress" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project       = var.project_id
  region        = local.automation_region
  name          = local.restricted_egress_connector_name
  network       = google_compute_network.restricted_egress[0].name
  ip_cidr_range = var.restricted_egress_connector_cidr
  min_instances = 2
  max_instances = 3

  depends_on = [
    google_compute_subnetwork.restricted_egress,
  ]
}

resource "google_compute_router" "restricted_egress" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project = var.project_id
  name    = local.restricted_egress_router_name
  region  = local.automation_region
  network = google_compute_network.restricted_egress[0].id
}

resource "google_compute_router_nat" "restricted_egress" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project                             = var.project_id
  region                              = local.automation_region
  name                                = local.restricted_egress_nat_name
  router                              = google_compute_router.restricted_egress[0].name
  nat_ip_allocate_option              = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat  = "ALL_SUBNETWORKS_ALL_IP_RANGES"
  enable_endpoint_independent_mapping = true
}

resource "google_compute_firewall" "restricted_egress_metadata_deny" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project     = var.project_id
  name        = local.restricted_egress_metadata_rule_name
  network     = google_compute_network.restricted_egress[0].name
  description = "Deny serverless connector egress to the GCE metadata endpoint."
  direction   = "EGRESS"
  priority    = 900
  destination_ranges = [
    "169.254.169.254/32",
  ]
  target_tags = [
    "vpc-connector",
  ]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_compute_firewall" "restricted_egress_non_public_deny" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project            = var.project_id
  name               = local.restricted_egress_non_public_rule_name
  network            = google_compute_network.restricted_egress[0].name
  description        = "Deny serverless connector egress to private, link-local, loopback, and CGNAT destinations."
  direction          = "EGRESS"
  priority           = 1000
  destination_ranges = local.restricted_egress_non_public_ranges
  target_tags = [
    "vpc-connector",
  ]

  deny {
    protocol = "all"
  }

  log_config {
    metadata = "INCLUDE_ALL_METADATA"
  }
}

resource "google_logging_metric" "restricted_egress_blocked_attempts" {
  count = local.enable_restricted_egress_resources ? 1 : 0

  project     = var.project_id
  name        = "restricted_egress_blocked_attempts"
  description = "Count of firewall-denied outbound connections from the TidingsIQ restricted-egress connector."
  filter      = <<-EOT
logName="projects/${var.project_id}/logs/compute.googleapis.com%2Ffirewall"
jsonPayload.disposition="DENIED"
(
  jsonPayload.rule_details.reference:"${local.restricted_egress_metadata_rule_name}"
  OR jsonPayload.rule_details.reference:"${local.restricted_egress_non_public_rule_name}"
)
EOT
}

resource "google_monitoring_alert_policy" "restricted_egress_blocked_attempts" {
  count = local.enable_restricted_egress_resources && local.enable_notification_email ? 1 : 0

  project               = var.project_id
  display_name          = "TidingsIQ Restricted Egress Blocks"
  combiner              = "OR"
  enabled               = true
  notification_channels = [google_monitoring_notification_channel.pipeline_email[0].name]

  conditions {
    display_name = "Restricted egress blocked outbound traffic within the last hour"

    condition_threshold {
      filter          = "resource.type=\"gce_subnetwork\" AND metric.type=\"logging.googleapis.com/user/${google_logging_metric.restricted_egress_blocked_attempts[0].name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.5
      duration        = "0s"

      aggregations {
        alignment_period     = "3600s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = []
      }

      trigger {
        count = 1
      }
    }
  }

  alert_strategy {
    auto_close = "7200s"
  }

  documentation {
    mime_type = "text/markdown"
    content   = "Firewall logs show that the TidingsIQ restricted-egress connector attempted to reach blocked private, internal, or metadata destinations within the last hour."
  }
}
