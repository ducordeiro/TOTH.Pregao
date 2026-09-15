import tempfile
import unittest
from datetime import date
from pathlib import Path

from etl.connectors import ConnectorError
from etl.models import PageResult, OpportunityItem, MatchResult
from etl.service import ETLSyncService, SyncRequest
from scripts.update_opportunity_database import (
    CheckedPublications, InitializedRepository, PreservingPublicationMapper, pending_units,
)

FILTERS = {"date_from": "2026-09-13", "date_to": "2026-09-13", "modality_codes": [6]}


def record():
    return {"numeroControlePNCP": "12345678000199-1-000001/2026", "anoCompra": 2026,
            "sequencialCompra": 1, "numeroCompra": "1", "numeroCnpj": "12345678000199",
            "objetoCompra": "Cadeiras", "dataPublicacaoPncp": "2026-09-13T09:00:00"}


class FakePages:
    def __init__(self, pages):
        self.pages = pages

    def iter_endpoint(self, *args):
        yield from self.pages


class PublicationUpdateTests(unittest.TestCase):
    def test_queue_is_recent_first_and_resumes_completed_units(self):
        units = pending_units(date(2026, 9, 12), date(2026, 9, 13), {"2026-09-13:1": {}})
        self.assertEqual(len(units), 37)
        self.assertEqual(units[0], ("2026-09-13:2", "2026-09-13", 2))
        self.assertEqual(units[-1], ("2026-09-12:19", "2026-09-12", 19))

    def test_incomplete_and_repeated_pages_are_rejected(self):
        row = record()
        page = PageResult([row], 1, 2, "https://pncp.test", {"data": [row], "totalRegistros": 2})
        for pages in ([page], [page, page]):
            with self.subTest(pages=len(pages)), self.assertRaises(ConnectorError):
                list(CheckedPublications(FakePages(pages)).iter_endpoint("publicacao", {}))
        empty = PageResult([], 1, 0, "https://pncp.test", {"data": [], "totalRegistros": 0})
        self.assertEqual(len(list(CheckedPublications(FakePages([empty])).iter_endpoint("publicacao", {}))), 1)

    def test_publication_preserves_metadata_items_and_search_index(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = InitializedRepository(Path(directory) / "test.sqlite3")
            repo.initialize()
            mapper = PreservingPublicationMapper(repo)
            original = mapper.map(record())
            original.uf = "SP"
            original.proposal_end_at = "2026-09-30T12:00:00"
            original.items = [OpportunityItem(source_item_id="1", title="Cadeira ergonomica", description="Cadeira ergonomica", item_number="1")]
            run = repo.create_run("pncp", "test", {})
            _, identity = repo.persist_record(run_id=run, source_endpoint="test", request_url="https://pncp.test",
                                              raw_payload={}, opportunity=original, match=MatchResult())
            row = {**record(), "objetoCompra": "Mobiliario atualizado"}
            page = PageResult([row], 1, 1, "https://pncp.test", {"data": [row], "totalRegistros": 1})
            service = ETLSyncService(repo, CheckedPublications(FakePages([page])), mapper)
            result = service.sync(SyncRequest(endpoint="publicacao", filters=FILTERS, fetch_details=False, max_pages=None, max_records=None))
            self.assertEqual(result["status"], "success")
            saved = repo.get_opportunity(identity)
            self.assertEqual(saved["opportunity"]["uf"], "SP")
            self.assertEqual(saved["opportunity"]["proposal_end_at"], "2026-09-30T12:00:00")
            self.assertEqual(len(saved["items"]), 1)
            self.assertEqual(repo.list_opportunities({"keywords": ["ergonomica"]})["total"], 1)
            again = service.sync(SyncRequest(endpoint="publicacao", filters=FILTERS, fetch_details=False, max_pages=None, max_records=None))
            self.assertEqual(again["skipped"], 1)

    def test_partial_download_persists_records_but_run_is_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = InitializedRepository(Path(directory) / "test.sqlite3")
            row = record()
            page = PageResult([row], 1, 2, "https://pncp.test", {"data": [row], "totalRegistros": 2})
            service = ETLSyncService(repo, CheckedPublications(FakePages([page])), PreservingPublicationMapper(repo))
            with self.assertRaises(ConnectorError):
                service.sync(SyncRequest(endpoint="publicacao", filters=FILTERS, fetch_details=False, max_pages=None, max_records=None))
            with repo.connect() as connection:
                run = connection.execute("SELECT * FROM etl_runs WHERE id=?", (repo.last_run_id,)).fetchone()
            self.assertEqual(run["status"], "failed")
            self.assertEqual(run["total_inserted"], 1)
            self.assertEqual(repo.list_opportunities({})["total"], 1)


if __name__ == "__main__":
    unittest.main()
