/* @bruin
name: gold.scoring_eval_labels
type: bq.sql
connection: bigquery-default

materialization:
  type: table

columns:
  - name: article_id
    type: string
    checks:
      - name: not_null
      - name: unique
  - name: default_feed_label
    type: string
  - name: positivity_label
    type: string
  - name: suitability_label
    type: string
  - name: link_label
    type: string
  - name: review_notes
    type: string
  - name: reviewed_by
    type: string
  - name: reviewed_at
    type: timestamp
@bruin */

select
  cast(null as string) as article_id,
  cast(null as string) as default_feed_label,
  cast(null as string) as positivity_label,
  cast(null as string) as suitability_label,
  cast(null as string) as link_label,
  cast(null as string) as review_notes,
  cast(null as string) as reviewed_by,
  cast(null as timestamp) as reviewed_at
limit 0
