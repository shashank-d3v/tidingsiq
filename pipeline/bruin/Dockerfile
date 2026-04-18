FROM python:3.11.13-slim-bookworm@sha256:cec9aa7aa96eea4fa036e9b82be1e6b325f2e3707f462d885868df51ec0a4b47 AS bruin-fetch

ARG BRUIN_VERSION=0.11.527
ARG BRUIN_ARCHIVE=bruin_Linux_x86_64.tar.gz
ARG BRUIN_SHA256=ad7690c2c517cfb3bfd4e94423ea36b40ae0b57901ecf0edd3d436a33e6097ad

ENV BRUIN_ARCHIVE="${BRUIN_ARCHIVE}" \
    BRUIN_RELEASE_URL="https://github.com/bruin-data/bruin/releases/download/v${BRUIN_VERSION}/${BRUIN_ARCHIVE}" \
    BRUIN_SHA256="${BRUIN_SHA256}"

RUN python - <<'PY'
import hashlib
import os
import pathlib
import tarfile
import urllib.request

url = os.environ["BRUIN_RELEASE_URL"]
expected_sha256 = os.environ["BRUIN_SHA256"]
archive_path = pathlib.Path("/tmp/bruin.tar.gz")
extract_dir = pathlib.Path("/opt/bruin")

with urllib.request.urlopen(url) as response:
    archive_path.write_bytes(response.read())

actual_sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
if actual_sha256 != expected_sha256:
    raise SystemExit(
        f"Bruin archive checksum mismatch: expected {expected_sha256}, got {actual_sha256}"
    )

extract_dir.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive_path, "r:gz") as archive:
    archive.extractall(extract_dir)
PY

RUN test -x /opt/bruin/bruin

FROM ghcr.io/astral-sh/uv:0.10.8@sha256:f99c19c9683591761e0dc9d80db421b17d8c004adf4ac4031cac1fc92777f091 AS uv-bin

FROM python:3.11.13-slim-bookworm@sha256:cec9aa7aa96eea4fa036e9b82be1e6b325f2e3707f462d885868df51ec0a4b47

ARG GIT_PACKAGE_VERSION=1:2.39.5-0+deb12u3
ARG TIDINGSIQ_UID=10001
ARG TIDINGSIQ_GID=10001

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/tidingsiq \
    PATH="/usr/local/bin:${PATH}"

RUN apt-get update \
    && apt-get install -y --no-install-recommends "git=${GIT_PACKAGE_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${TIDINGSIQ_GID}" tidingsiq \
    && useradd --uid "${TIDINGSIQ_UID}" --gid "${TIDINGSIQ_GID}" --create-home --home-dir "${HOME}" --shell /bin/sh tidingsiq

WORKDIR /workspace

COPY pipeline/bruin/requirements.lock ./pipeline/bruin/requirements.lock
RUN python -m pip install --require-hashes -r pipeline/bruin/requirements.lock

COPY --from=uv-bin /uv /usr/local/bin/uv
COPY --from=uv-bin /uvx /usr/local/bin/uvx
COPY --from=bruin-fetch /opt/bruin/bruin /usr/local/bin/bruin
COPY --chown=tidingsiq:tidingsiq pipeline ./pipeline
COPY --chown=tidingsiq:tidingsiq scripts ./scripts
COPY --chown=tidingsiq:tidingsiq pipeline/bruin/container-entrypoint.sh /usr/local/bin/container-entrypoint.sh

RUN chmod 0755 /usr/local/bin/bruin /usr/local/bin/container-entrypoint.sh /usr/local/bin/uv /usr/local/bin/uvx \
    && mkdir -p "${HOME}/.bruin" \
    && ln -sf /usr/local/bin/uv "${HOME}/.bruin/uv" \
    && ln -sf /usr/local/bin/uvx "${HOME}/.bruin/uvx" \
    && chown -R tidingsiq:tidingsiq /workspace "${HOME}"

USER tidingsiq:tidingsiq

ENTRYPOINT ["/usr/local/bin/container-entrypoint.sh"]
CMD ["run", "pipeline/bruin/pipeline.yml"]
