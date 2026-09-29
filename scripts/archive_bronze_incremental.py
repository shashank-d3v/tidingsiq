"""Checkpointed, export-only Bronze archival. Source rows remain available to Silver.

The ingestion contract assigns a fresh ingested_at to every replacement/backfill.
Only ingestions older than the retention delay are checkpointed. A GCS generation
lock serializes writers; a crashed worker fails closed until its lock is reviewed.
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery


class ObjectStore:
    def __init__(self, prefix: str):
        match = re.fullmatch(r"gs://([a-z0-9._-]+)/([a-zA-Z0-9/_-]+)", prefix.rstrip("/"))
        if not match:
            raise ValueError("Use gs://bucket/path with a simple archive path")
        self.bucket, self.prefix = match.groups()
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        self.session = AuthorizedSession(credentials)

    def url(self, name):
        return f"https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/{quote(self.prefix+'/'+name, safe='')}"

    def read(self, name):
        response = self.session.get(self.url(name), params={"alt": "media"}, timeout=60)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    def write(self, name, value, generation=None):
        params = {"uploadType": "media", "name": self.prefix + "/" + name}
        if generation is not None:
            params["ifGenerationMatch"] = generation
        response = self.session.post(
            f"https://storage.googleapis.com/upload/storage/v1/b/{self.bucket}/o",
            params=params, data=json.dumps(value),
            headers={"Content-Type": "application/json"}, timeout=60,
        )
        response.raise_for_status()
        return response.json()["generation"]

    def unlock(self, generation):
        response = self.session.delete(self.url("archive.lock"), params={"ifGenerationMatch": generation}, timeout=60)
        response.raise_for_status()


def bounds(checkpoint, now, retention_days):
    if retention_days < 1:
        raise ValueError("retention_days must be positive")
    upper = (now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=retention_days))
    lower = datetime.fromisoformat(checkpoint["cutoff_timestamp"]) if checkpoint else datetime(1970, 1, 1, tzinfo=timezone.utc)
    if lower.tzinfo is None:
        raise ValueError("Checkpoint timestamp must have a timezone")
    return lower, upper


def run(project, prefix, retention_days=45, dry_run=False):
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project):
        raise ValueError("Invalid project ID")
    store = ObjectStore(prefix)
    client = bigquery.Client(project=project)
    config = bigquery.QueryJobConfig(maximum_bytes_billed=20_000_000_000,
                                    labels={"component": "bronze_archive"})
    def query(sql, job_config=config):
        return client.query(sql, job_config=job_config).result()
    lock = None
    snapshot = None
    summary = {"status": "failed", "delete_after_export": False, "dry_run": dry_run}
    try:
        if not dry_run:
            lock = store.write("archive.lock", {"started_at": datetime.now(timezone.utc).isoformat()}, generation=0)
        checkpoint = store.read("checkpoint.json")
        lower, upper = bounds(checkpoint, datetime.now(timezone.utc), retention_days)
        summary.update(cutoff_timestamp=upper.isoformat(), previous_cutoff_timestamp=lower.isoformat())
        if lower >= upper:
            summary.update(status="noop", candidate_row_count=0, exported_row_count=0)
            return summary
        predicate = f"ingested_at >= TIMESTAMP('{lower.isoformat()}') AND ingested_at < TIMESTAMP('{upper.isoformat()}')"
        source = f"{project}.bronze.gdelt_news_raw"
        if dry_run:
            count = next(iter(query(f"SELECT COUNT(*) n FROM `{source}` WHERE {predicate}")))["n"]
            summary.update(status="dry_run", candidate_row_count=count)
            return summary
        batch_id = uuid.uuid4().hex
        snapshot = f"{project}.bronze.archive_snapshot_{batch_id}"
        query(f"CREATE TABLE `{snapshot}` OPTIONS(expiration_timestamp=TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 2 DAY)) AS SELECT * FROM `{source}` WHERE {predicate}")
        candidate = client.get_table(snapshot).num_rows
        uri = f"{prefix.rstrip('/')}/batches/{batch_id}/*.parquet"
        summary.update(candidate_row_count=candidate, archive_uri=uri, snapshot_table=snapshot)
        if candidate:
            query(f"EXPORT DATA OPTIONS(uri='{uri}', format='PARQUET', compression='SNAPPY', overwrite=false) AS SELECT * FROM `{snapshot}`")
            external = bigquery.ExternalConfig("PARQUET")
            external.source_uris = [uri]
            validation_config = bigquery.QueryJobConfig(table_definitions={"exported": external}, maximum_bytes_billed=20_000_000_000)
            # Compare the complete multiset, including duplicate multiplicity, before checkpointing.
            validation = next(iter(query(f"""
              WITH actual AS (SELECT TO_JSON_STRING(t) row_value, COUNT(*) n FROM exported t GROUP BY 1),
              expected AS (SELECT TO_JSON_STRING(t) row_value, COUNT(*) n FROM `{snapshot}` t GROUP BY 1)
              SELECT COUNTIF(a.n IS NULL OR e.n IS NULL OR a.n != e.n) mismatches
              FROM actual a FULL JOIN expected e USING(row_value)
            """, validation_config)))["mismatches"]
            if validation:
                raise RuntimeError(f"Archive validation found {validation} mismatched row groups")
        summary.update(previous_manifest=("manifests/" + checkpoint["batch_id"] + ".json" if checkpoint and checkpoint.get("batch_id") else None),
                       bootstrap_archive_uri=checkpoint.get("archive_uri") if checkpoint and not checkpoint.get("batch_id") else None)
        summary.update(status="exported" if candidate else "noop", exported_row_count=candidate,
                       completed_at=datetime.now(timezone.utc).isoformat(), batch_id=batch_id)
        # Immutable manifest first; checkpoint only after all Parquet data is verified.
        store.write(f"manifests/{batch_id}.json", summary, generation=0)
        store.write("checkpoint.json", summary)
        client.delete_table(snapshot)
        snapshot = None
        return summary
    finally:
        if lock is not None:
            store.unlock(lock)


def prune_archived(project, prefix, retention_days=90, max_delete_rows=20000):
    """Remove only checkpoint-covered rows outside the complete Silver horizon."""
    if retention_days < 90 or max_delete_rows < 1:
        raise ValueError("Hot retention must be at least 90 days and deletion cap positive")
    store = ObjectStore(prefix)
    lock = store.write("archive.lock", {"operation": "prune", "started_at": datetime.now(timezone.utc).isoformat()}, generation=0)
    try:
        checkpoint = store.read("checkpoint.json")
        if not checkpoint:
            raise RuntimeError("Cannot prune without a verified archive checkpoint")
        archived_through, cutoff = bounds(checkpoint, datetime.now(timezone.utc), retention_days)
        cutoff = min(archived_through, cutoff)
        source = f"{project}.bronze.gdelt_news_raw"
        predicate = (f"ingested_at < TIMESTAMP('{cutoff.isoformat()}') AND "
                     f"COALESCE(published_at, ingested_at) < TIMESTAMP('{cutoff.isoformat()}')")
        client = bigquery.Client(project=project)
        config = bigquery.QueryJobConfig(maximum_bytes_billed=20_000_000_000,
                                        labels={"component": "bronze_retention"})
        count = next(iter(client.query(f"SELECT COUNT(*) n FROM `{source}` WHERE {predicate}", job_config=config).result()))["n"]
        if count > max_delete_rows:
            raise RuntimeError(f"Prune backlog {count} exceeds deletion cap {max_delete_rows}")
        if count:
            client.query(f"""BEGIN TRANSACTION;
                ASSERT (SELECT COUNT(*) FROM `{source}` WHERE {predicate}) <= {max_delete_rows} AS 'Prune cap exceeded';
                DELETE FROM `{source}` WHERE {predicate};
                COMMIT TRANSACTION;""", job_config=config).result()
        print(f"BRONZE_RETENTION_SUMMARY status=success candidate_row_count={count} cutoff_timestamp={cutoff.isoformat()}")
    finally:
        store.unlock(lock)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--archive-uri-prefix", required=True)
    parser.add_argument("--retention-days", type=int, default=45)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--prune-after-days", type=int)
    parser.add_argument("--max-delete-rows", type=int, default=20000)
    args = parser.parse_args()
    try:
        summary = run(args.project_id, args.archive_uri_prefix, args.retention_days, args.dry_run)
        if args.prune_after_days is not None and not args.dry_run:
            prune_archived(args.project_id, args.archive_uri_prefix, args.prune_after_days, args.max_delete_rows)
    except Exception as exc:
        print(f"BRONZE_ARCHIVE_SUMMARY status=failed error={type(exc).__name__}:{exc}")
        return 1
    print("BRONZE_ARCHIVE_SUMMARY " + " ".join(f"{key}={value}" for key, value in summary.items()))
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
