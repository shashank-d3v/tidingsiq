import importlib.util
from datetime import datetime, timedelta, timezone
import copy
import io
from contextlib import redirect_stdout
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec=importlib.util.spec_from_file_location('publisher',Path(__file__).parents[1]/'publish_static_feed.py')
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)

class Store:
    def __init__(self,fail=None,corrupt=False):
        self.data={}
        self.fail=fail
        self.corrupt=corrupt
        self.writes=[]
    def metadata(self,name): return {'generation':'1'} if name in self.data else None
    def read(self,name): return b'bad bytes' if self.corrupt and name.endswith('.gz') else self.data[name]
    def write(self,name,data,generation):
        if name==self.fail: raise RuntimeError('upload failed')
        self.writes.append(name)
        self.data[name]=data

class PublisherTests(unittest.TestCase):
    def metrics(self):
        now=datetime.now(timezone.utc)
        return now,{'audit_run_at':now,'latest_gold_ingested_at':now,'gold_row_count':100,'latest_bronze_ingestion_is_complete':True,'consecutive_complete_low_volume_run_count':0}
    def test_stale_incomplete_and_failed_metrics_are_rejected(self):
        now,metrics=self.metrics()
        publisher.validate_freshness(metrics,now)
        for change in [{'audit_run_at':now-timedelta(days=1)}, {'latest_gold_ingested_at':now-timedelta(days=2)}, {'latest_bronze_ingestion_is_complete':False}, {'consecutive_complete_low_volume_run_count':3}, {'gold_row_count':0}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                publisher.validate_freshness({**metrics,**change},now)
    def execution(self, now):
        return {'name': 'projects/test/locations/region/jobs/pipeline/executions/one',
                'startTime': (now-timedelta(minutes=5)).isoformat(),
                'completionTime': (now+timedelta(seconds=1)).isoformat(),
                'taskCount': 1, 'succeededCount': 1,
                'conditions': [{'type': 'Completed', 'state': 'CONDITION_SUCCEEDED'}]}

    def test_metrics_must_be_from_latest_successful_execution(self):
        now, metrics = self.metrics()
        execution = self.execution(now)
        publisher.validate_pipeline_execution(execution, metrics, now)
        failures = [
            {'conditions': [{'type': 'Completed', 'state': 'CONDITION_FAILED'}]},
            {'conditions': []}, {'succeededCount': 0}, {'failedCount': 1},
            {'cancelledCount': 1}, {'runningCount': 1}, {'reconciling': True},
            {'completionTime': None}, {'startTime': (now+timedelta(seconds=1)).isoformat()},
            {'completionTime': (now-timedelta(seconds=1)).isoformat()},
        ]
        for change in failures:
            with self.subTest(change=change), self.assertRaises(ValueError):
                publisher.validate_pipeline_execution({**execution, **change}, metrics, now)

    def test_latest_execution_is_read_without_falling_back_to_old_success(self):
        response = Mock()
        response.json.return_value = {'executions': [{'name': 'new-failed'}, {'name': 'old-success'}]}
        session = Mock()
        session.get.return_value = response
        with patch.object(publisher.google.auth, 'default', return_value=(object(), None)), \
                patch.object(publisher, 'AuthorizedSession', return_value=session):
            pipeline = publisher.Pipeline('test-project', 'asia-south1', 'pipeline')
        self.assertEqual(pipeline.latest()['name'], 'new-failed')
        self.assertEqual(session.get.call_args.kwargs['params'], {'pageSize': 1})
        response.json.return_value = {}
        with self.assertRaisesRegex(ValueError, 'No pipeline execution'):
            pipeline.latest()

    def test_precommit_pipeline_failure_keeps_previous_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            manifest = self.artifacts(folder)
            store = Store()
            old = json.dumps({'latest_data_at': '2026-09-29T00:30:00+00:00'}).encode()
            store.data['manifest.json'] = old
            guard = Mock(side_effect=ValueError('pipeline changed'))
            with self.assertRaisesRegex(ValueError, 'pipeline changed'):
                publisher.publish_files(store, folder, manifest, before_commit=guard)
            guard.assert_called_once()
            self.assertTrue(store.writes)  # uploads completed before the final guard
            self.assertNotIn('manifest.json', store.writes)
            self.assertEqual(store.data['manifest.json'], old)

    def artifacts(self,folder):
        source=folder/'source.json'
        source.write_text(json.dumps([{'article_id':'a','serving_date':'2026-09-30','title':'School opens today','url':'https://example.com/a','happy_factor':80}]))
        manifest=publisher.snapshot.build(source,folder,datetime(2026,9,30).date())
        manifest['latest_data_at']='2026-09-30T00:30:00+00:00'
        return manifest
    def test_manifest_is_last_and_failed_upload_preserves_old_edition(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);manifest=self.artifacts(folder)
            for store in [Store(),Store(fail=manifest['ranges']['7']['file']+'.gz'),Store(corrupt=True)]:
                old=json.dumps({'latest_data_at':'2026-09-29T00:30:00+00:00'}).encode()
                store.data['manifest.json']=old
                if store.fail or store.corrupt:
                    with self.assertRaises((RuntimeError,ValueError)):publisher.publish_files(store,folder,manifest)
                    self.assertEqual(store.data['manifest.json'],old)
                else:
                    publisher.publish_files(store,folder,manifest)
                    self.assertEqual(store.writes[-1],'manifest.json')
                    self.assertEqual(json.loads(store.data['manifest.json']),manifest)
    def test_old_publisher_cannot_replace_newer_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);manifest=self.artifacts(folder);store=Store()
            store.data['manifest.json']=json.dumps({'latest_data_at':'2026-10-01T00:30:00+00:00'}).encode()
            with self.assertRaises(ValueError):publisher.publish_files(store,folder,manifest)
            self.assertEqual(store.writes,[])

    def test_invalid_counts_assignments_and_gzip_never_write(self):
        for failure in ('counts','assignment','audit','gzip','version'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);manifest=self.artifacts(folder);store=Store()
                if failure=='counts':manifest['ranges']['7']['story_count']=2
                elif failure=='assignment':manifest['story_count']=2
                elif failure=='version':manifest['matcher_version']='unknown'
                elif failure=='audit':(folder/'story-audit.json').write_text('{}')
                else:(folder/(manifest['ranges']['7']['file']+'.gz')).write_bytes(b'bad')
                with self.assertRaises((ValueError,KeyError,OSError)):publisher.publish_files(store,folder,manifest)
                self.assertEqual(store.writes,[])

    def test_suppression_shift_warns_and_publication_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);manifest=self.artifacts(folder);store=Store()
            store.data['manifest.json']=json.dumps({'latest_data_at':'2026-09-29T00:30:00+00:00','suppression_ratio':.2}).encode()
            output=io.StringIO()
            with redirect_stdout(output):publisher.publish_files(store,folder,manifest)
            self.assertIn('STATIC_FEED_DEDUP status=warning',output.getvalue())
            self.assertEqual(store.writes[-1],'manifest.json')
            self.assertTrue(any(name.startswith('_audit/') for name in store.writes))

    def test_generation_conflict_preserves_winning_manifest(self):
        class ConcurrentStore(Store):
            def write(self,name,data,generation):
                if name=='manifest.json':
                    self.data[name]=b'winning edition'
                    raise RuntimeError('generation precondition failed')
                return super().write(name,data,generation)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);manifest=self.artifacts(folder);store=ConcurrentStore()
            with self.assertRaisesRegex(RuntimeError,'precondition'):publisher.publish_files(store,folder,manifest)
            self.assertEqual(store.data['manifest.json'],b'winning edition')

    def test_failed_run_with_fresh_metrics_never_exports(self):
        now, metrics = self.metrics()
        client = Mock()
        client.query.return_value.result.return_value = [metrics]
        pipeline = Mock()
        pipeline.latest.return_value = {**self.execution(now),
            'conditions': [{'type': 'Completed', 'state': 'CONDITION_FAILED'}]}
        with patch.object(publisher.bigquery, 'Client', return_value=client), \
                patch.object(publisher, 'Pipeline', return_value=pipeline), \
                patch.object(publisher, 'Store') as store, \
                patch('sys.argv', ['publish', '--project', 'tidingsiq-dev', '--bucket', 'test',
                                  '--pipeline-region', 'asia-south1', '--pipeline-job', 'tidingsiq-pipeline']):
            with self.assertRaisesRegex(ValueError, 'has not succeeded'):
                publisher.main()
        self.assertEqual(client.query.call_count, 1)
        store.assert_not_called()

    def test_execution_changes_during_export_preserve_the_old_edition(self):
        now, metrics = self.metrics()
        article = {'article_id': 'a', 'serving_date': now.date(), 'published_at': now,
                   'ingested_at': now, 'title': 'Community garden opens today',
                   'url': 'https://example.com/news', 'happy_factor': 80}
        execution = self.execution(now)
        for latest in ({**execution, 'name': execution['name'] + '-new'},
                       {**execution, 'conditions': []}):
            with self.subTest(latest=latest):
                client = Mock()
                client.query.return_value.result.side_effect = [[metrics], [article]]
                pipeline = Mock()
                pipeline.latest.side_effect = [execution, latest]
                store = Store()
                old = json.dumps({'latest_data_at': (now-timedelta(days=1)).isoformat()}).encode()
                store.data['manifest.json'] = old
                with patch.object(publisher.bigquery, 'Client', return_value=client), \
                        patch.object(publisher, 'Pipeline', return_value=pipeline), \
                        patch.object(publisher, 'Store', return_value=store), \
                        patch('sys.argv', ['publish', '--project', 'tidingsiq-dev', '--bucket', 'test',
                                          '--pipeline-region', 'asia-south1', '--pipeline-job', 'tidingsiq-pipeline']):
                    with self.assertRaises(ValueError):
                        publisher.main()
                self.assertTrue(store.writes)
                self.assertNotIn('manifest.json', store.writes)
                self.assertEqual(store.data['manifest.json'], old)

    def test_overnight_ingestion_publishes_previous_day_articles(self):
        now,metrics=self.metrics()
        yesterday=now-timedelta(days=1)
        article={'article_id':'article-1','serving_date':yesterday.date(),
                 'published_at':yesterday,'ingested_at':now,'happy_factor':80,
                 'tone_score':4,'title':'A new community garden','url':'https://example.com/news',
                 'source_name':'example.com','language':'en','mentioned_country_name':'India'}
        class Job:
            total_bytes_billed=100
            def __init__(self,rows):self.rows=rows
            def result(self):return iter(self.rows)
        class Client:
            def query(self,sql,job_config):
                return Job([metrics] if 'pipeline_run_metrics' in sql else [article])
        store=Store()
        pipeline = Mock()
        pipeline.latest.return_value = self.execution(now)
        with patch.object(publisher.bigquery,'Client',return_value=Client()),patch.object(publisher,'Store',return_value=store),patch.object(publisher,'Pipeline',return_value=pipeline),patch('sys.argv',['publish','--project','tidingsiq-dev','--bucket','test-bucket','--pipeline-region','asia-south1','--pipeline-job','tidingsiq-pipeline']):
            publisher.main()
        manifest=json.loads(store.data['manifest.json'])
        self.assertEqual(manifest['as_of'],str(now.date()))
        self.assertEqual(manifest['ranges']['7']['rows'],1)
        self.assertEqual(pipeline.latest.call_count, 2)
