FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/root/.local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://getbruin.com/install/cli | sh

WORKDIR /workspace

COPY pipeline/bruin/pyproject.toml ./pipeline/bruin/pyproject.toml
COPY pipeline/bruin/uv.lock ./pipeline/bruin/uv.lock
RUN pip install "pandas>=2.2.0" "google-cloud-bigquery>=3.25.0"

COPY pipeline ./pipeline
COPY scripts ./scripts
COPY pipeline/bruin/container-entrypoint.sh /usr/local/bin/container-entrypoint.sh

RUN chmod +x /usr/local/bin/container-entrypoint.sh \
    && git init /workspace \
    && git config --global --add safe.directory /workspace

ENTRYPOINT ["/usr/local/bin/container-entrypoint.sh"]
CMD ["run", "pipeline/bruin/pipeline.yml"]
