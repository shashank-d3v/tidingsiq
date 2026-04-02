#!/bin/sh
set -eu

BRUIN_CONFIG_PATH="${BRUIN_CONFIG_PATH:-/workspace/.bruin.yml}"
BRUIN_ENVIRONMENT="${BRUIN_ENVIRONMENT:-default}"
BRUIN_CONNECTION_NAME="${BRUIN_CONNECTION_NAME:-bigquery-default}"
BRUIN_PROJECT_ID="${BRUIN_PROJECT_ID:-${GOOGLE_CLOUD_PROJECT:-}}"
BRUIN_BIGQUERY_LOCATION="${BRUIN_BIGQUERY_LOCATION:-${BIGQUERY_LOCATION:-US}}"

if [ -z "${BRUIN_PROJECT_ID}" ]; then
  echo "BRUIN_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set." >&2
  exit 1
fi

cat > "${BRUIN_CONFIG_PATH}" <<EOF
default_environment: ${BRUIN_ENVIRONMENT}
environments:
  ${BRUIN_ENVIRONMENT}:
    connections:
      google_cloud_platform:
        - name: "${BRUIN_CONNECTION_NAME}"
          project_id: "${BRUIN_PROJECT_ID}"
          location: "${BRUIN_BIGQUERY_LOCATION}"
          use_application_default_credentials: true
EOF

exec bruin "$@"

