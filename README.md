# TidingsIQ: Positive News Intelligence Pipeline

TidingsIQ is a portfolio data engineering project focused on building a low-cost, cloud-native ELT pipeline for global news intelligence.

The system ingests news metadata from GDELT, loads and transforms it in BigQuery using Bruin, provisions infrastructure with Terraform, and serves sentiment-filtered results through a Streamlit interface.

## Objective

The goal of TidingsIQ is to surface positive global news based on a configurable Happy Factor threshold, while demonstrating practical skills in:

- Terraform
- BigQuery
- Bruin
- Streamlit
- ELT pipeline design
- data quality and idempotent processing

## Planned Architecture

- **Infrastructure:** Terraform on GCP
- **Ingestion and orchestration:** Bruin Python assets
- **Transformation:** Bruin SQL assets on BigQuery
- **Serving layer:** Streamlit
- **Source:** GDELT Global Knowledge Graph

## Status

Project scaffold initialized. Documentation and data contract definition are in progress.