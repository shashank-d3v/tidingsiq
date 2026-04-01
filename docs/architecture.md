# TidingsIQ Architecture

## Overview

TidingsIQ is a low-cost, cloud-native ELT pipeline that ingests global news metadata from GDELT, stores and transforms it in BigQuery through Bruin-managed assets, and serves sentiment-filtered results through a Streamlit application.

The pipeline is designed to demonstrate practical data engineering skills across infrastructure provisioning, ingestion, transformation, data quality, idempotent processing, and lightweight analytical serving.

## Core Components

### 1. Infrastructure Layer
Terraform provisions the required Google Cloud Platform resources, including:
- BigQuery datasets
- service accounts
- IAM bindings

### 2. Source Layer
The upstream source is the GDELT Global Knowledge Graph, which provides frequently updated global news metadata along with tone and emotional signals.

### 3. Ingestion Layer
Bruin Python assets are responsible for:
- fetching GDELT data
- applying retry and backoff logic
- minimizing unnecessary fields before storage
- loading the result into BigQuery Bronze tables

### 4. Transformation Layer
Bruin SQL assets running on BigQuery will model the data through three layers:

- **Bronze**: raw ingested records
- **Silver**: cleaned, normalized, deduplicated records
- **Gold**: sentiment-enriched, UI-ready positive news feed

### 5. Serving Layer
A Streamlit application will query the Gold layer in BigQuery and allow users to filter results using a configurable Happy Factor threshold.

## Architectural Principles

- low-cost by design
- cloud-native and reproducible
- idempotent pipeline behavior
- quality checks close to transformation logic
- clear separation between raw, refined, and serving models

## Initial Data Flow

GDELT → Bruin Python Asset → BigQuery Bronze → Bruin SQL Assets → BigQuery Gold → Streamlit UI

## Planned Repository Mapping

- `infra/terraform/` for infrastructure provisioning
- `pipeline/bruin/` for ingestion and transformation assets
- `app/streamlit/` for the frontend
- `docs/` for design and implementation documentation