"""Publish a fresh, eligible-only static feed; switch manifest only after validation."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote

import google.auth
from google.auth.transport.requests import AuthorizedSession
from google.cloud import bigquery

spec = importlib.util.spec_from_file_location('static_snapshot', Path(__file__).resolve().parents[1] / 'app/static/build_snapshot.py')
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)

class Store:
    def __init__(self, bucket):
        self.bucket = bucket
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        self.session = AuthorizedSession(credentials)

    def metadata(self, name):
        r = self.session.get(f'https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/{quote(name, safe="")}', timeout=60)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    def read(self, name):
        r = self.session.get(f'https://storage.googleapis.com/storage/v1/b/{self.bucket}/o/{quote(name, safe="")}', params={'alt':'media'}, timeout=60)
        r.raise_for_status()
        return r.content

    def write(self, name, data, generation):
        r = self.session.post(f'https://storage.googleapis.com/upload/storage/v1/b/{self.bucket}/o',
            params={'uploadType':'media','name':name,'ifGenerationMatch':generation}, data=data,
            headers={'Content-Type':'application/gzip' if name.endswith('.gz') else 'application/json'}, timeout=60)
        r.raise_for_status()
        return r.json()



class Pipeline:
    """Read-only success evidence from the configured Cloud Run pipeline job."""
    def __init__(self, project, region, job):
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        self.session = AuthorizedSession(credentials)
        self.parent = f'projects/{project}/locations/{region}/jobs/{job}'

    def latest(self):
        # The API sorts executions by creation time descending. Never fall back
        # to an older success when the latest execution failed or is still running.
        response = self.session.get(f'https://run.googleapis.com/v2/{self.parent}/executions',
                                    params={'pageSize': 1}, timeout=60)
        response.raise_for_status()
        executions = response.json().get('executions', [])
        if not executions:
            raise ValueError('No pipeline execution available')
        return executions[0]


def validate_pipeline_execution(execution, metrics, now):
    completed = any(condition.get('type') == 'Completed'
                    and condition.get('state') == 'CONDITION_SUCCEEDED'
                    for condition in execution.get('conditions', []))
    tasks = execution.get('taskCount', 0)
    if (not execution.get('name') or not completed or tasks < 1
            or execution.get('succeededCount', 0) != tasks
            or execution.get('failedCount', 0) or execution.get('cancelledCount', 0)
            or execution.get('runningCount', 0) or execution.get('reconciling', False)):
        raise ValueError('Latest pipeline execution has not succeeded')
    try:
        start = datetime.fromisoformat(execution['startTime'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(execution['completionTime'].replace('Z', '+00:00'))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise ValueError('Missing pipeline execution timestamps') from exc
    audit = metrics['audit_run_at']
    audit = audit.replace(tzinfo=audit.tzinfo or timezone.utc)
    if (start.tzinfo is None or end.tzinfo is None
            or not start <= audit <= end <= now + timedelta(minutes=5)):
        raise ValueError('Metrics do not belong to the latest successful pipeline execution')


def validate_freshness(metrics, now):
    for key, max_age in [('audit_run_at', timedelta(hours=18)), ('latest_gold_ingested_at', timedelta(hours=36))]:
        value = metrics.get(key)
        if not isinstance(value, datetime):
            raise ValueError(f'Missing freshness field: {key}')
        value = value.replace(tzinfo=value.tzinfo or timezone.utc)
        if not now-max_age <= value <= now+timedelta(minutes=5):
            raise ValueError(f'Stale or future metrics: {key}')
    if metrics.get('latest_bronze_ingestion_is_complete') is not True:
        raise ValueError('Latest live source window is incomplete; keep last good edition')
    if metrics.get('consecutive_complete_low_volume_run_count', 0) >= 3:
        raise ValueError('Latest pipeline has a failing low-volume streak')
    if not metrics.get('gold_row_count',0):
        raise ValueError('Gold is empty')


def validate_story_artifacts(folder, manifest):
    if manifest.get('matcher_version') != snapshot.matcher.MATCHER_VERSION:
        raise ValueError('Missing matcher version')
    assignments = {}
    for entry in manifest['ranges'].values():
        raw = (folder / entry['file']).read_bytes()
        if not re.fullmatch(r'feed-(7|30)d-' + hashlib.sha256(raw).hexdigest()[:16] + r'\.json', entry['file']):
            raise ValueError('Artifact hash mismatch')
        zipped = (folder / (entry['file'] + '.gz')).read_bytes()
        if gzip.decompress(zipped) != raw or len(raw) != entry['bytes'] or len(zipped) != entry['gzip_bytes']:
            raise ValueError('Invalid artifact size or compression')
        rows = json.loads(raw)
        ids = [r['article_id'] for r in rows]
        stories = [r.get('story_id') for r in rows]
        if (len(ids) != len(set(ids)) or not all(stories)
                or len(rows) != entry['rows'] or len(rows) != entry['article_count']
                or len(set(stories)) != entry['story_count']):
            raise ValueError('Invalid story assignments or counts')
        for row in rows:
            if assignments.setdefault(row['article_id'], row['story_id']) != row['story_id']:
                raise ValueError('Inconsistent cross-range story assignment')
    if set(manifest['ranges']) != {'7', '30'}:
        raise ValueError('Missing serving ranges')
    as_of = datetime.fromisoformat(manifest['as_of']).date()
    full = {r['article_id']: r for r in json.loads((folder / manifest['ranges']['30']['file']).read_bytes())}
    for days, entry in manifest['ranges'].items():
        actual = json.loads((folder / entry['file']).read_bytes())
        expected = [r for r in full.values() if (as_of-timedelta(days=int(days))).isoformat() <= r['serving_date'] <= as_of.isoformat()]
        if actual != expected:
            raise ValueError('Invalid serving-range membership')
    audit = json.loads((folder / 'story-audit.json').read_bytes())
    membership = {m['article_id']: c['story_id'] for c in audit['clusters'] for m in c['members']}
    member_count = sum(len(c['members']) for c in audit['clusters'])
    if (membership != assignments or member_count != len(assignments)
            or len(assignments) != manifest['article_count']
            or len(set(assignments.values())) != manifest['story_count']
            or audit['metrics'] != {k: manifest[k] for k in audit['metrics']}):
        raise ValueError('Audit does not match public assignments')


def publish_files(store, folder, manifest, before_commit=None):
    validate_story_artifacts(folder, manifest)
    previous = store.metadata('manifest.json')
    generation = previous['generation'] if previous else 0
    if previous:
        old = json.loads(store.read('manifest.json'))
        if old.get('latest_data_at', '') > manifest['latest_data_at']:
            raise ValueError('Refusing to replace a newer edition')
    audit = (folder / 'story-audit.json').read_bytes()
    audit_name = '_audit/story-' + hashlib.sha256(audit).hexdigest() + '.json'
    if not store.metadata(audit_name):
        store.write(audit_name, audit, 0)
    if store.read(audit_name) != audit:
        raise ValueError('Uploaded audit differs')
    if previous and 'suppression_ratio' in old:
        shift = abs(manifest['suppression_ratio'] - old['suppression_ratio'])
        if shift > .15:
            print('STATIC_FEED_DEDUP status=warning suppression_shift=' + str(shift), flush=True)
    for item in manifest['ranges'].values():
        raw = (folder / item['file']).read_bytes()
        zipped = (folder / (item['file']+'.gz')).read_bytes()
        if gzip.decompress(zipped) != raw:
            raise ValueError('Invalid gzip artifact')
        for name, data in [(item['file'],raw),(item['file']+'.gz',zipped)]:
            if not store.metadata(name):
                store.write(name,data,0)
            if hashlib.sha256(store.read(name)).digest() != hashlib.sha256(data).digest():
                raise ValueError(f'Uploaded content differs: {name}')
    # GCS generation precondition prevents an overlapping publisher rolling back a winner.
    if before_commit is not None:
        before_commit()
    store.write('manifest.json',json.dumps(manifest,separators=(',',':')).encode(),generation)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True)
    p.add_argument('--bucket',required=True)
    p.add_argument('--location',default='asia-south1', help='BigQuery location')
    p.add_argument('--pipeline-region', required=True, help='Cloud Run pipeline region')
    p.add_argument('--pipeline-job', required=True, help='Cloud Run pipeline job name')
    args=p.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]',args.project):
        raise ValueError('Invalid project ID')
    for value in (args.pipeline_region, args.pipeline_job):
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,62}', value):
            raise ValueError('Invalid pipeline region or job name')
    pipeline = Pipeline(args.project, args.pipeline_region, args.pipeline_job)
    execution = pipeline.latest()
    client=bigquery.Client(project=args.project,location=args.location)
    config=bigquery.QueryJobConfig(maximum_bytes_billed=500_000_000,labels={'component':'static_publish'})
    metrics=next(iter(client.query(f'''SELECT audit_run_at, latest_gold_ingested_at,
        latest_bronze_ingestion_is_complete, consecutive_complete_low_volume_run_count, gold_row_count
        FROM `{args.project}.gold.pipeline_run_metrics` ORDER BY audit_run_at DESC LIMIT 1''',job_config=config).result()),None)
    if metrics is None:
        raise ValueError('No pipeline metrics available')
    now=datetime.now(timezone.utc)
    validate_freshness(dict(metrics),now)
    validate_pipeline_execution(execution, metrics, now)
    as_of=metrics['latest_gold_ingested_at'].date()
    config.query_parameters=[bigquery.ScalarQueryParameter('as_of','DATE',as_of)]
    job=client.query(f'''SELECT {', '.join(snapshot.FIELDS)} FROM `{args.project}.gold.positive_news_feed`
        WHERE is_positive_feed_eligible = TRUE
        AND serving_date BETWEEN DATE_SUB(@as_of, INTERVAL 30 DAY) AND @as_of
        ORDER BY happy_factor DESC, COALESCE(published_at, ingested_at) DESC, article_id DESC''',job_config=config)
    rows=[dict(row) for row in job.result()]
    # Publication dates can precede an overnight ingestion date. Freshness is
    # checked against successful pipeline metrics, not article publication dates.
    if not rows:
        raise ValueError('No eligible articles in the serving window')
    if any(not row['title'] or not row['url'] or row['happy_factor'] is None or not 65<=float(row['happy_factor'])<=100 for row in rows):
        raise ValueError('Export violates the eligible-feed contract')
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        source=root/'source.json'
        source.write_text(json.dumps(rows,default=lambda value:value.isoformat()))
        manifest=snapshot.build(source,root/'data',as_of)
        manifest.update(source='Eligible news feed',generated_at=now.isoformat(),latest_data_at=metrics['latest_gold_ingested_at'].isoformat())
        def confirm_pipeline():
            latest = pipeline.latest()
            validate_pipeline_execution(latest, metrics, datetime.now(timezone.utc))
            if latest['name'] != execution['name']:
                raise ValueError('Pipeline execution changed during publication')
        publish_files(Store(args.bucket),root/'data',manifest, before_commit=confirm_pipeline)
    print('STATIC_FEED_PUBLISH status=success '+json.dumps({'as_of':str(as_of),'ranges':manifest['ranges'],'bytes_billed':job.total_bytes_billed,'dedup':{key:manifest[key] for key in ('matcher_version','article_count','story_count','suppression_ratio','exact_match_count','fuzzy_match_count','syndication_match_count','largest_cluster')}}),flush=True)

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        print(f'STATIC_FEED_PUBLISH status=failed error={type(exc).__name__}: {exc}',flush=True)
        raise
