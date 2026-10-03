# TidingsIQ Documentation

Start with the [project overview and screenshots](../README.md). The maintained
guides below describe the static deployment and warehouse code as reviewed on
**2 October 2026**. Historical observations and cost estimates are separated so
an old plan is not mistaken for the current operating procedure.

## Product and Design

| Guide | Use it for |
|---|---|
| [Architecture](architecture.md) | Components, data flow, public/warehouse boundaries and retention |
| [Static dashboard](../app/static/README.md) | Local setup, feed behavior, payload sizes and artifact isolation |
| [Data contract](data_contract.md) | Warehouse schemas, public fields, date semantics and deduplication |
| [Happy Factor](happy_factor.md) | Active scoring formula, eligibility, badge colours and limitations |
| [GDELT findings](gdelt_findings.md) | Source mappings and explicitly dated validation samples |
| [Screenshots](screenshots/README.md) | Capture date, source, viewports and image inventory |

## Build and Operate

| Guide | Use it for |
|---|---|
| [Deployment](deployment_plan.md) | Current release process, schedules, frontend and publisher builds |
| [Story deduplication](durable_story_deduplication.md) | Matching rules, measured release checks, daily safeguards and rollback |
| [Operations runbook](operations_runbook.md) | Diagnosis, publishing, emergency stop, archival and repair |
| [Engagement measurement](engagement_rollout_20261002.md) | Page-load engagement, article clicks, legacy-client rejection and week-one review |
| [Runtime IAM](iam_minimum_roles.md) | Provisioned role scopes and legacy-identity distinction |
| [Release checklist](public_release_checklist.md) | Artifact, browser, source and publication checks |
| [Terraform](../infra/terraform/README.md) | Module inputs, defaults, optional infrastructure and state |
| [Bruin pipeline](../pipeline/bruin/README.md) | Assets, bounded ingestion, validation and container execution |
| [Operational scripts](../scripts/README.md) | Publisher/report/archive workers and explicit recovery helpers |

## Status and Reference

- [Roadmap](roadmap.md): completed work and justified next steps.
- [V3 scoring shadow](gold_scoring_v3_shadow.md): experimental model, not promoted.
- [Legacy Streamlit](../app/streamlit/README.md): retained development app, not public production.
- [History](history/README.md): preserved incident, sizing, rollout and cost evidence.
- [October 2 traffic/cost baseline](traffic_billing_analysis_20261002.md): dated aggregate workload costs, request proxies and measurement limitations.

## Keeping This Set Current

Update the relevant canonical guide when behavior changes, and keep README links
pointing to it rather than duplicating long procedures. Label live observations
with a date. Keep incident evidence historical. Capture real screenshots after
the feed has loaded, with no sensitive console/credential content. Run relative
link/image checks after moving or deleting documents. A docs update does not
justify production changes or refreshing a cost estimate without new evidence.
