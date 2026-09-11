import tempfile
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from etl import ETLRepository, PNCPMapper, OpportunityClassifier
from etl.models import PageResult
from scripts import enrich_missing_pncp_items as worker
from etl.connectors import ConnectorError


class PriorityEnrichmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = ETLRepository(Path(self.temp.name) / "test.sqlite3")
        self.repo.initialize()
        self.run = self.repo.create_run("pncp", "item_enrichment_batch", {})
        self.ids = []
        for seq, start, end in ((1, "2025-01-01", "2025-02-01"),
                                (2, "2026-09-01", "2026-09-20"),
                                (3, "2026-09-15", "2026-09-25")):
            opp = PNCPMapper().map({
                "numeroControlePNCP": f"12345678000199-1-{seq:06d}/2026",
                "numeroCnpj": "12345678000199", "anoCompra": 2026,
                "sequencialCompra": seq, "objetoCompra": "Moveis",
                "dataAberturaProposta": start, "dataEncerramentoProposta": end,
            })
            _, oid = self.repo.persist_record(run_id=self.run, source_endpoint="test",
                request_url="https://pncp.test", raw_payload={}, opportunity=opp,
                match=OpportunityClassifier().classify(opp, {}))
            self.ids.append(oid)

    def pending(self, **kwargs):
        return worker._load_missing(self.repo, "2026-06-01", 20, scope="all", as_of="2026-09-10", **kwargs)

    def test_active_then_future_then_history_and_retry_exclusion(self):
        self.assertEqual([r["id"] for r in self.pending()], [self.ids[1], self.ids[2], self.ids[0]])
        row = self.pending()[0]
        self.repo.save_failed_source_record(run_id=self.run, source="pncp", source_endpoint="item_enrichment_batch",
            request_url="https://pncp.test", raw_payload={}, error_message="timeout", external_key=row["external_key"])
        with self.repo.connect() as db, db:
            db.execute("UPDATE source_records SET captured_at='2000-01-01' WHERE status='failed'")
        self.assertEqual(len(self.pending(retry_failures_after_hours=0)), 3)
        self.assertEqual(len(self.pending(retry_failures_after_hours=0, exclude_run_id=self.run)), 2)

    def test_newest_publication_precedes_open_status_and_missing_dates(self):
        with self.repo.connect() as db, db:
            db.execute("UPDATE opportunities SET published_at='2026-09-10T09:00:00' WHERE id=?", (self.ids[0],))
            db.execute("UPDATE opportunities SET published_at='2026-09-09T10:00:00' WHERE id=?", (self.ids[1],))
            db.execute("UPDATE opportunities SET published_at='' WHERE id=?", (self.ids[2],))
        self.assertEqual([row['id'] for row in self.pending()], self.ids)
        with self.repo.connect() as db, db:
            db.execute("UPDATE opportunities SET published_at='2026-09-10T10:00:00' WHERE id=?", (self.ids[2],))
        self.assertEqual([row['id'] for row in self.pending()], [self.ids[2], self.ids[0], self.ids[1]])

    def enrich(self, pages):
        return worker._enrich_one(repository=self.repo,
            connector=SimpleNamespace(iter_items=lambda *args: iter(pages)), mapper=PNCPMapper(),
            run_id=self.run, row=self.pending()[0], item_max_pages=2, dry_run=False)

    def test_complete_items_persist_and_enter_search_index(self):
        payload = [{"numeroItem": 1, "descricao": "Cadeira ortopedica teste", "quantidade": 2}]
        outcome = self.enrich([PageResult(payload, 1, 1, "https://dadosabertos.compras.gov.br/items", {"totalRegistros": 1})])
        self.assertEqual(outcome[:2], ("updated", 1))
        with self.repo.connect() as db:
            matches = db.execute("SELECT opportunity_id FROM opportunity_search WHERE opportunity_search MATCH 'ortopedica'").fetchall()
        self.assertEqual([r[0] for r in matches], [self.ids[1]])
        self.assertNotIn(self.ids[1], [r["id"] for r in self.pending()])

    def test_partial_or_duplicate_items_never_persist(self):
        payload = [{"numeroItem": 1, "descricao": "Cadeira", "quantidade": 2}]
        for page in (PageResult(payload, 1, 2, "https://pncp.test", {}),
                     PageResult(payload, 1, 1, "https://pncp.test", {"totalRegistros": 2}),
                     PageResult(payload*2, 1, 1, "https://pncp.test", {"totalRegistros": 2})):
            with self.subTest(page=page), self.assertRaises(RuntimeError):
                self.enrich([page])
            self.assertFalse(self.repo.opportunity_has_items(self.ids[1]))

    def test_rate_limit_defers_next_requests_without_hiding_failure(self):
        pacer = Mock()
        client = worker.PacedHttpJsonClient(pacer=pacer, timeout=4, retries=0)
        with patch.object(worker.HttpJsonClient, "get", side_effect=ConnectorError("HTTP 429")):
            with self.assertRaises(ConnectorError):
                client.get("https://pncp.test")
        pacer.wait.assert_called_once()
        pacer.defer.assert_called_once_with(60)

    def test_every_retry_is_paced_and_429_is_not_lost_after_success(self):
        pacer = Mock()
        client = worker.PacedHttpJsonClient(pacer=pacer, retries=1, sleeper=Mock())
        error = ConnectorError('HTTP 429')
        error.__cause__ = urllib.error.HTTPError('https://test', 429, 'limited', {'Retry-After': '120'}, None)
        with patch.object(worker.HttpJsonClient, 'get', side_effect=[error, 'ok']):
            self.assertEqual(client.get('https://test'), 'ok')
        self.assertEqual(pacer.wait.call_count, 2)
        pacer.defer.assert_called_once_with(120)

    def test_permanent_http_error_is_not_retried(self):
        client = worker.PacedHttpJsonClient(pacer=Mock(), retries=3, sleeper=Mock())
        error = ConnectorError('HTTP 404')
        error.__cause__ = urllib.error.HTTPError('https://test', 404, 'missing', {}, None)
        with patch.object(worker.HttpJsonClient, 'get', side_effect=error) as request:
            with self.assertRaises(ConnectorError):
                client.get('https://test')
        self.assertEqual(request.call_count, 1)

    def test_waiting_worker_rechecks_new_cooldown(self):
        pacer = worker.RequestPacer(0.5)
        now = [0.0]
        sleeps = []
        def sleep(delay):
            sleeps.append(delay)
            if len(sleeps) == 1:
                pacer.defer(60)
            now[0] += delay
        with patch.object(worker.time, 'monotonic', side_effect=lambda: now[0]), patch.object(worker.time, 'sleep', side_effect=sleep):
            pacer.wait()
            pacer.wait()
        self.assertEqual(sleeps, [0.5, 59.5])
        self.assertEqual(now[0], 60)


if __name__ == "__main__":
    unittest.main()
