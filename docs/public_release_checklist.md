# Public Release Checklist

## Containment

- Confirm the documented GDELT default remains `http://data.gdeltproject.org/gdeltv2`.
- Confirm deployed runtimes reject `GDELT_BASE_URL` overrides that do not resolve to `data.gdeltproject.org`.
- Confirm Bronze fails closed on corrupt ZIPs, unreadable ZIP members, wrong row widths, malformed timestamps, elevated malformed-row ratios, and sudden accepted-row collapse.
- Confirm the existing Cloud Monitoring pipeline failure alert path is active for containment failures.

## Public App

- Confirm the app remains public and unauthenticated on the direct Cloud Run `run.app` URL.
- Confirm the Cloud Run app service ingress accepts direct internet traffic rather than requiring a load balancer path.
- Confirm the app service account remains read-only against `gold` and the app still serves only the bounded Gold-backed UI.
- Confirm the Cloud Run service reports `Ready=True` after deploy.
- Confirm normal browsing smoke tests pass on the direct `run.app` URL:
  - page refreshes
  - pagination
  - filter changes

## Rollout Notes

- The current portfolio posture intentionally favors simpler operations over edge hardening.
- If traffic later justifies stricter protection, the optional AppEdge path can be re-enabled in Terraform.
- Keep `app_max_instance_count` conservative so unexpected public traffic cannot scale the service far.

## Accepted Residual Risk

- Accepted upstream residual risk: TidingsIQ intentionally uses the documented HTTP GDELT feed as the validated default path.
- This is a containment decision, not an HTTPS migration.
- Residual risk is limited by host restriction, payload validation, anomaly detection, and fail-closed execution, but not eliminated while the upstream default remains HTTP.
- Accepted public-app residual risk: the app no longer has Cloud Armor rate limiting or load-balancer buffering in front of Cloud Run, so abusive traffic is mitigated mainly by the app's bounded query model and conservative Cloud Run scaling.
