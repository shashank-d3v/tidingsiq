import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import archive_bronze_incremental as worker


class IncrementalArchiveTest(unittest.TestCase):
    def test_bounds_preserve_exact_checkpoint_and_utc_cutoff(self):
        lower, upper = worker.bounds({"cutoff_timestamp": "2026-08-13T00:00:00+00:00"}, datetime(2026, 9, 28, 12, tzinfo=timezone.utc), 45)
        self.assertEqual(lower.isoformat(), "2026-08-13T00:00:00+00:00")
        self.assertEqual(upper.isoformat(), "2026-08-14T00:00:00+00:00")

    def setup_clients(self, store_cls, client_cls, mismatches=0):
        store = store_cls.return_value
        store.read.return_value = {"cutoff_timestamp": "1970-01-01T00:00:00+00:00"}
        store.write.return_value = "123"
        client = client_cls.return_value
        client.get_table.return_value = SimpleNamespace(num_rows=3)
        client.query.side_effect = [MagicMock(result=MagicMock(return_value=rows)) for rows in ([], [], [{"mismatches": mismatches}])]
        return store, client

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_verified_export_advances_checkpoint_after_immutable_manifest(self, store_cls, client_cls):
        store, client = self.setup_clients(store_cls, client_cls)
        result = worker.run("example-project", "gs://example/archive")
        self.assertEqual(result["exported_row_count"], 3)
        names = [call.args[0] for call in store.write.call_args_list]
        self.assertEqual(names[0], "archive.lock")
        self.assertTrue(names[1].startswith("manifests/"))
        self.assertEqual(names[2], "checkpoint.json")
        store.unlock.assert_called_once_with("123")
        client.delete_table.assert_called_once()
        self.assertTrue(all("DELETE FROM" not in call.args[0].upper() for call in client.query.call_args_list))

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_parquet_mismatch_does_not_advance_checkpoint_or_discard_snapshot(self, store_cls, client_cls):
        store, client = self.setup_clients(store_cls, client_cls, mismatches=1)
        with self.assertRaisesRegex(RuntimeError, "mismatched"):
            worker.run("example-project", "gs://example/archive")
        self.assertEqual([call.args[0] for call in store.write.call_args_list], ["archive.lock"])
        client.delete_table.assert_not_called()
        store.unlock.assert_called_once_with("123")

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_repeated_run_does_not_export_again(self, store_cls, client_cls):
        store, client = self.setup_clients(store_cls, client_cls)
        store.read.return_value = {"cutoff_timestamp": "2999-01-01T00:00:00+00:00"}
        self.assertEqual(worker.run("example-project", "gs://example/archive")["status"], "noop")
        client.query.assert_not_called()
        self.assertEqual(store.write.call_count, 1)

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_lock_conflict_cannot_export_or_release_another_workers_lock(self, store_cls, client_cls):
        store, client = self.setup_clients(store_cls, client_cls)
        store.write.side_effect = RuntimeError("generation precondition")
        with self.assertRaises(RuntimeError):
            worker.run("example-project", "gs://example/archive")
        client.query.assert_not_called()
        store.unlock.assert_not_called()

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_export_failure_leaves_checkpoint_unchanged(self, store_cls, client_cls):
        store, client = self.setup_clients(store_cls, client_cls)
        client.query.side_effect = [MagicMock(result=MagicMock(return_value=[])), RuntimeError("export failed")]
        with self.assertRaises(RuntimeError):
            worker.run("example-project", "gs://example/archive")
        self.assertEqual(store.write.call_count, 1)
        store.unlock.assert_called_once_with("123")
        client.delete_table.assert_not_called()

    def test_retention_rejects_shorter_than_silver_horizon(self):
        with self.assertRaises(ValueError):
            worker.prune_archived("example-project", "gs://example/archive", 45)

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_retention_requires_completed_checkpoint(self, store_cls, client_cls):
        store_cls.return_value.read.return_value = None
        with self.assertRaisesRegex(RuntimeError, "checkpoint"):
            worker.prune_archived("example-project", "gs://example/archive")
        client_cls.assert_not_called()
        store_cls.return_value.unlock.assert_called_once()

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_retention_cap_prevents_deletion(self, store_cls, client_cls):
        store_cls.return_value.read.return_value = {"cutoff_timestamp": "2026-08-15T00:00:00+00:00"}
        client_cls.return_value.query.return_value.result.return_value = [{"n": 20001}]
        with self.assertRaisesRegex(RuntimeError, "exceeds deletion cap"):
            worker.prune_archived("example-project", "gs://example/archive")
        self.assertEqual(client_cls.return_value.query.call_count, 1)

    @patch.object(worker.bigquery, "Client")
    @patch.object(worker, "ObjectStore")
    def test_retention_limits_by_checkpoint_and_publication_date(self, store_cls, client_cls):
        store_cls.return_value.read.return_value = {"cutoff_timestamp": "2020-01-01T00:00:00+00:00"}
        client_cls.return_value.query.return_value.result.return_value = [{"n": 12}]
        worker.prune_archived("example-project", "gs://example/archive")
        sql = client_cls.return_value.query.call_args_list[-1].args[0]
        self.assertIn("2020-01-01T00:00:00+00:00", sql)
        self.assertIn("COALESCE(published_at, ingested_at)", sql)
        self.assertIn("ASSERT", sql)
        self.assertIn("BEGIN TRANSACTION", sql)
