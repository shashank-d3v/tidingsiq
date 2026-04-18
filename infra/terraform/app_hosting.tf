locals {
  app_container_image = trimspace(var.app_container_image) != "" ? trimspace(var.app_container_image) : "${local.artifact_registry_location}-docker.pkg.dev/${var.project_id}/${var.app_artifact_repository_id}/tidingsiq-streamlit:latest"
  app_gold_table      = trimspace(var.app_gold_table) != "" ? trimspace(var.app_gold_table) : "${var.project_id}.gold.positive_news_feed"
}

resource "google_artifact_registry_repository" "app" {
  count = var.enable_app_hosting ? 1 : 0

  project       = var.project_id
  location      = local.artifact_registry_location
  repository_id = var.app_artifact_repository_id
  format        = "DOCKER"
  description   = "Container images for the TidingsIQ Streamlit app."
  labels        = local.common_labels
}

resource "google_artifact_registry_repository_iam_member" "app_cloud_run_service_agent_reader" {
  count = var.enable_app_hosting ? 1 : 0

  project    = var.project_id
  location   = google_artifact_registry_repository.app[0].location
  repository = google_artifact_registry_repository.app[0].repository_id
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${local.cloud_run_service_agent}"
}

resource "google_cloud_run_v2_service" "app" {
  count = var.enable_app_hosting ? 1 : 0

  project             = var.project_id
  location            = local.automation_region
  name                = var.app_service_name
  deletion_protection = false
  ingress             = local.app_edge_enabled ? "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER" : "INGRESS_TRAFFIC_ALL"
  labels              = local.common_labels

  template {
    service_account = google_service_account.app[0].email

    scaling {
      min_instance_count = var.app_min_instance_count
      max_instance_count = var.app_max_instance_count
    }

    containers {
      image = local.app_container_image

      ports {
        container_port = 8080
      }

      env {
        name  = "TIDINGSIQ_GCP_PROJECT"
        value = var.project_id
      }

      env {
        name  = "TIDINGSIQ_GOLD_TABLE"
        value = local.app_gold_table
      }

      resources {
        limits = {
          cpu    = "1"
          memory = var.app_memory_limit
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository_iam_member.app_cloud_run_service_agent_reader,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "app_invoker" {
  count = var.enable_app_hosting && var.app_allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = google_cloud_run_v2_service.app[0].location
  name     = google_cloud_run_v2_service.app[0].name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
