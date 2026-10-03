# Traffic and billing snapshot — 2 October 2026

Verified read-only around 18:28 IST. This is historical baseline evidence, not
a current balance or forecast. Request-log coverage was September 2 through
October 2 at 18:22 IST, with 14,769 records below the 50,000 query limit.

September project-filtered Billing Reports: Cloud Run INR 771.05, Artifact
Registry INR 31.14, BigQuery INR 22.13, Cloud Storage INR 1.62; net subtotal
INR 825.94 before tax. Cloud Run contributes 93.35%. Service CPU/memory total
INR 761.86 versus job CPU/memory INR 8.65. BigQuery Analysis shows 1.03 TiB.

Footfall proxies: 79 homepage requests; 65 after excluding explicit bot/headless
agents, across 29 addresses. Static/story revisions have 16 browser-like homepage
requests across six addresses. These include self/QA and possibly disguised bots;
neither requests nor addresses are confirmed people. In IST, October 1 had 3,338
total requests but only two homepage requests.

Of 8,111 static/story revision requests, 7,936 (97.84%) hit legacy Streamlit
health and host-config endpoints from one address with Mac Chrome 150. The client was not identified; the request pattern alone does not establish
who operated it.
Old revisions logged 1,962 WebSocket upgrades, median 301 seconds, with summed
duration 584,141 seconds (162.26 hours). Overlap means this is not billable
instance time. Static/story requests sum to approximately 73 seconds latency
and have no WebSocket upgrades. This supports persistent old connections as a
compute driver but does not establish an exact invoice savings percentage.

Four homepage requests carry a GitHub repository referrer. Static homepage loads
include iPhone and Android agents. Feed requests split 18 seven-day and seven
thirty-day requests, including QA; no customer preference rate can be inferred.
No engagement or returning-reader measurement existed at this snapshot.

Sources: authenticated Google Cloud Billing Reports (project services/SKUs),
Cloud Run request logs and service configuration. See [the follow-up implementation](engagement_rollout_20261002.md).
