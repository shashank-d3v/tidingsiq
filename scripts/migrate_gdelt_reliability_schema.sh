#!/bin/sh
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <gcp-project-id> [bigquery-location]" >&2
  exit 2
fi

project_id="$1"
location="${2:-asia-south1}"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
migration_file="${script_dir}/migrations/20260826_gdelt_reliability.sql"

case "$project_id" in
  *[!a-z0-9:-]*|'')
    echo "Invalid GCP project ID: $project_id" >&2
    exit 2
    ;;
esac

migration_sql=$(sed "s/__PROJECT_ID__/${project_id}/g" "$migration_file")
bq query \
  --project_id="$project_id" \
  --location="$location" \
  --use_legacy_sql=false \
  "$migration_sql"
