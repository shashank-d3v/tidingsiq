# Public Release Checklist

## Containment

- Confirm the documented GDELT default remains `http://data.gdeltproject.org/gdeltv2`.
- Confirm deployed runtimes reject `GDELT_BASE_URL` overrides that do not resolve to `data.gdeltproject.org`.
- Confirm Bronze fails closed on corrupt ZIPs, unreadable ZIP members, wrong row widths, malformed timestamps, elevated malformed-row ratios, and sudden accepted-row collapse.
- Confirm the existing Cloud Monitoring pipeline failure alert path is active for containment failures.

## Public App Edge

- Confirm the app remains public and unauthenticated, but the public entrypoint is the external HTTPS load balancer rather than the direct `run.app` URL.
- Confirm the Cloud Run app service ingress is limited to Google Cloud load balancers and internal traffic.
- Confirm the load balancer hostname resolves to the Terraform-managed global IP and the Google-managed certificate is active.
- Confirm Cloud Armor is attached to the load balancer backend service.
- Confirm the initial per-IP throttle rule is configured as `120 requests / 60 seconds / IP` with preview mode enabled for monitor-first rollout.
- Confirm load balancer backend logging is enabled at `sample_rate = 1.0`.
- Confirm request-volume, preview-throttle, enforced-throttle, Cloud Run pressure, and BigQuery query-volume or billed-bytes charts appear on the app dashboard.
- Confirm the Cloud Run instance-pressure alert is present and targets the app service.
- Confirm normal browsing smoke tests pass through the load balancer:
  - page refreshes
  - pagination
  - filter changes
  - multiple users behind one office or home NAT IP

## Rollout Notes

- Keep the throttle rule in preview mode for the first 7 days and inspect preview exceed logs before enforcement.
- If preview logs show negligible false positives, turn preview off without changing the threshold first.
- Only consider tightening toward `90 requests / 60 seconds / IP` after a second observation window.
- Expect very frequent refreshes from one IP or heavily shared NATs to be the first legitimate patterns that may hit enforced limits.

## Accepted Residual Risk

- Accepted upstream residual risk: TidingsIQ intentionally uses the documented HTTP GDELT feed as the validated default path.
- This is a containment decision, not an HTTPS migration.
- Residual risk is limited by host restriction, payload validation, anomaly detection, and fail-closed execution, but not eliminated while the upstream default remains HTTP.
- Accepted public-app residual risk: a shared office or home NAT IP may occasionally encounter preview or enforced throttling sooner than an individual household user would.
