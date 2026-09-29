"""Repair bounded daily 23:45-00:30 UTC GKG samples; stage all windows, merge once."""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from google.cloud import bigquery


def windows(start: date, end: date):
    if end < start or (end - start).days > 30:
        raise ValueError("Repair must cover 1 to 31 days")
    for offset in range((end - start).days + 1):
        upper = datetime.combine(start + timedelta(days=offset), time(0, 30), tzinfo=timezone.utc)
        yield upper - timedelta(minutes=45), upper


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--start-date", type=date.fromisoformat, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--extra-window-end", action="append", default=[], type=datetime.fromisoformat,
                        help="Additional exact timezone-aware window end, for historical intraday canaries")
    args = parser.parse_args()
    planned = list(windows(args.start_date, args.end_date))
    if len(args.extra_window_end) > 8:
        raise ValueError("At most eight extra windows are allowed")
    for upper in args.extra_window_end:
        if upper.tzinfo is None or upper.minute % 15 or upper.second or upper.microsecond:
            raise ValueError("Extra windows must be timezone-aware quarter-hour boundaries")
        planned.append((upper - timedelta(minutes=45), upper))
    planned = sorted(set(planned))
    if planned[-1][1] >= datetime.now(timezone.utc) - timedelta(hours=2):
        raise ValueError("Repair windows must already be published")
    spec = importlib.util.spec_from_file_location("repair_gdelt", Path(__file__).resolve().parents[1] / "pipeline/bruin/assets/bronze/gdelt_news_raw.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    os.environ.update(BRUIN_PROJECT_ID=args.project_id, GDELT_EXPLICIT_INTERVAL_REQUESTED="true", GDELT_MAX_FILES="4")
    client = bigquery.Client(project=args.project_id)
    source = client.get_table(f"{args.project_id}.bronze.gdelt_news_raw")
    stage_id = f"{args.project_id}.bronze.repair_{uuid.uuid4().hex}"
    staging = bigquery.Table(stage_id, schema=source.schema)
    staging.expires = datetime.now(timezone.utc) + timedelta(days=2)
    client.create_table(staging)
    total = 0
    for lower, upper in planned:
        os.environ.update(BRUIN_START_DATETIME=lower.isoformat(), BRUIN_END_DATETIME=upper.isoformat())
        frame = module.materialize()
        if frame.empty or not frame["bronze_run_is_complete"].all() or not frame["bronze_run_is_backfill"].all():
            raise RuntimeError(f"Incomplete repair for {upper.date()}; source table unchanged, staged rows retained at {stage_id}")
        payload = io.BytesIO(frame.to_json(orient="records", lines=True, date_format="iso").encode("utf-8"))
        client.load_table_from_file(payload, stage_id, job_config=bigquery.LoadJobConfig(schema=source.schema, source_format="NEWLINE_DELIMITED_JSON", write_disposition="WRITE_APPEND")).result()
        total += len(frame)
        print(f"GDELT_REPAIR_STAGED date={upper.date()} rows={len(frame)} total={total}", flush=True)
    columns = [field.name for field in source.schema]
    update = ", ".join(f"`{col}`=s.`{col}`" for col in columns)
    names = ", ".join(f"`{col}`" for col in columns)
    values = ", ".join(f"s.`{col}`" for col in columns)
    # One merge regardless of window count; do not overwrite a more recent live ingestion.
    sql = f"""MERGE `{source.full_table_id.replace(':', '.')}` t
      USING (SELECT * FROM `{stage_id}` QUALIFY ROW_NUMBER() OVER(PARTITION BY source_record_id ORDER BY ingested_at DESC)=1) s
      ON t.source_record_id=s.source_record_id
      WHEN MATCHED AND t.ingested_at <= s.ingested_at THEN UPDATE SET {update}
      WHEN NOT MATCHED THEN INSERT ({names}) VALUES ({values})"""
    job = client.query(sql, job_config=bigquery.QueryJobConfig(maximum_bytes_billed=30_000_000_000, labels={"component": "gdelt_repair"}))
    job.result()
    print(f"GDELT_REPAIR_COMMITTED windows={len(planned)} staged_rows={total} affected_rows={job.num_dml_affected_rows} bytes_billed={job.total_bytes_billed} stage={stage_id}")
    # Staging retained for two days for reconciliation and retry diagnosis.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
