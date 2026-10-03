# TidingsIQ Roadmap

## Objective

Maintain a bounded, observable news pipeline and a useful public static feed
without tying visitor interactions to warehouse queries.

## Current State

Verified against code and deployment on **2 October 2026**:

- Terraform foundation, dedicated runtime identities, and scheduled Cloud Run jobs
- GDELT source-attempt tracking, bounded retries, completeness and low-volume checks
- Silver normalization and Gold guardrailed scoring with operational summaries
- Checkpointed archival with verified exports and capped pruning beyond 90 days
- Static Brief, selection-based Pulse, and Methodology deployed publicly
- Daily publisher with atomic manifest replacement and last-good-edition behavior
- Versioned story assignments with all eligible variants retained; browser filters
  precede representative selection for cards and statistics
- Same-origin page-lifetime engagement measurement with privacy opt-outs
- Request-based frontend billing, scale-to-zero, and a two-instance maximum
- Successful scheduled publications on October 1 and 2
- Current desktop/mobile screenshots and consolidated operating documentation

## Next Steps

1. Compare actual monthly billing and transfer usage with the dated planning
   estimate; consider billing export for durable attribution across services.
2. Measure cold load, memory, and filter responsiveness on representative mobile
   devices/networks as the feed grows. Browser layout checks are not a performance benchmark.
3. Broaden independent validation of the existing exact, syndication and bounded
   fuzzy matching; inspect false merges and missed rewrites across languages.
4. Keep tuning title guardrails with labelled evidence. The v3 shadow model needs
   evaluation before any promotion to the canonical serving table.
5. Add a repeatable CI/release workflow for the allowlisted frontend and publisher,
   including artifact isolation and publication failure tests.
6. Verify alert delivery end to end; configured notification policies do not by
   themselves prove messages reached a recipient.

## Conditional Future Work

- Smaller/incremental data chunks if measured payload or memory growth warrants them
- CDN/custom domain or edge throttling if actual traffic justifies the extra services
- Separate Terraform state and variables if a second environment becomes necessary
- Restricted egress only for a concrete private-network or IP-allowlisting requirement

The former query-per-filter Streamlit proposal is superseded by daily static
publication. Reintroducing request-driven BigQuery access is not on the current
roadmap. Completed build phases are summarized above instead of maintained as a
second implementation plan. See [historical evidence](history/README.md) for why
billing, archival, and serving decisions changed.
