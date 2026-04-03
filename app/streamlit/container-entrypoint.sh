#!/bin/sh
set -eu

exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8080}" \
  --server.headless=true
