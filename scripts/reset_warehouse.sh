#!/bin/sh
set -eu

PROJECT_ID="${1:-${PROJECT_ID:-}}"

if [ -z "${PROJECT_ID}" ]; then
  echo "Usage: scripts/reset_warehouse.sh <gcp-project-id>" >&2
  exit 1
fi

echo "Resetting warehouse tables in project ${PROJECT_ID}..."

bq query --use_legacy_sql=false "truncate table \`${PROJECT_ID}.bronze.gdelt_news_raw\`"
bq query --use_legacy_sql=false "truncate table \`${PROJECT_ID}.silver.gdelt_news_refined\`"
bq query --use_legacy_sql=false "truncate table \`${PROJECT_ID}.gold.positive_news_feed\`"
bq query --use_legacy_sql=false "truncate table \`${PROJECT_ID}.gold.pipeline_run_metrics\`"

bq query --use_legacy_sql=false "
declare drop_statements array<string>;

set drop_statements = (
  select array_agg(
    format('drop table \`%s.bronze_staging.%s\`', '${PROJECT_ID}', table_name)
  )
  from \`${PROJECT_ID}.bronze_staging.INFORMATION_SCHEMA.TABLES\`
  where table_type = 'BASE TABLE'
);

for statement in (
  select statement
  from unnest(drop_statements) as statement
)
do
  execute immediate statement.statement;
end for;
"

echo "Warehouse reset complete for ${PROJECT_ID}."
