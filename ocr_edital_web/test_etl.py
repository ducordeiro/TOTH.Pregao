import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from etl import ComprasGovMapper, ETLRepository, ETLSyncService, PNCPMapper, SyncRequest
from etl.connectors import ConnectorError, HttpJsonClient
from etl.models import FetchedPayload, PageResult
from etl.jobs import run_backfill, run_comprasgov_backfill


class FakePNCPConnector:
    SOURCE = "pncp"

    def __init__(self):
        self.description = "Aquisicao de cadeiras"

    def iter_endpoint(self, endpoint, filters, max_pages=None):
        record = {
            "numeroControlePNCP": "12345678000199-1-000001/2026",
            "numeroCnpj": "12345678000199",
            "anoCompra": 2026,
            "sequencialCompra": 1,
            "numeroCompra": "90001/2026",
            "objetoCompra": self.description,
        }
        yield PageResult([record], 1, 1, "https://pncp.test/proposta?pagina=1", {"data": [record]})

    def fetch_detail(self, cnpj, year, sequence):
        return FetchedPayload({
            "orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "Orgao Teste"},
            "unidadeOrgao": {
                "ufSigla": "SP",
                "municipioNome": "Mogi Mirim",
                "codigoUnidade": "123456",
            },
            "modalidadeId": 6,
            "modalidadeNome": "Pregao Eletronico",
            "dataPublicacaoPncp": "2026-08-05T09:00:00",
            "dataAberturaProposta": "2026-08-05T10:00:00",
            "dataEncerramentoProposta": "2026-08-06T10:00:00",
            "valorTotalEstimado": 1000,
        }, "https://pncp.test/detail")

    def iter_items(self, cnpj, year, sequence, max_pages=None):
        items = [
            {
                "numeroLote": "1",
                "numeroItem": "1",
                "materialOuServicoNome": "Cadeira",
                "descricao": "Cadeira A",
                "informacaoComplementar": "Assento estofado e base giratoria",
                "criterioJulgamentoNome": "Menor preco",
                "quantidade": 2,
                "valorUnitarioEstimado": 100,
            },
            {"numeroLote": "2", "numeroItem": "1", "descricao": "Cadeira B", "quantidade": 3, "valorUnitarioEstimado": 200},
        ]
        yield PageResult(items, 1, 1, "https://pncp.test/items", {"data": items})

    def fetch_documents(self, cnpj, year, sequence):
        return FetchedPayload({"data": [{
            "titulo": "Edital",
            "tipoDocumentoNome": "Edital",
            "url": "https://pncp.test/edital.pdf",
        }]}, "https://pncp.test/documents")


class FakeComprasGovConnector:
    SOURCE = "comprasgov"

    def iter_endpoint(self, endpoint, filters, max_pages=None):
        record = {
            "numeroControlePNCP": "12345678000199-1-000001/2026",
            "numeroCnpj": "12345678000199",
            "anoCompra": 2026,
            "sequencialCompra": 1,
            "numeroCompra": "90001/2026",
            "objetoCompra": "Registro complementar",
        }
        yield PageResult([record], 1, 1, "https://compras.test/contratacoes", {"resultado": [record]})


class FakeHttpResponse:
    class Headers:
        @staticmethod
        def get_content_charset():
            return "utf-8"

    headers = Headers()

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class FakeBackfillConnector:
    SOURCE = "pncp"

    def __init__(self, failures=None):
        self.calls = []
        self.failures = dict(failures or {})

    def iter_endpoint(self, endpoint, filters, max_pages=None):
        day = filters["dataInicial"]
        modality = int(filters["codigoModalidadeContratacao"])
        unit = (day, modality)
        self.calls.append(unit)
        remaining_failures = self.failures.get(unit, 0)
        if remaining_failures:
            self.failures[unit] = remaining_failures - 1
            raise RuntimeError(f"temporary failure for {day}/{modality}")
        record = {
            "numeroControlePNCP": f"12345678000199-1-{day}{modality:02d}/2026",
            "numeroCnpj": "12345678000199",
            "anoCompra": 2026,
            "sequencialCompra": int(f"{day[-4:]}{modality:02d}"),
            "numeroCompra": f"{day}/{modality}",
            "objetoCompra": f"Opportunity {day}/{modality}",
            "modalidadeId": modality,
            "dataPublicacaoPncp": f"{day[:4]}-{day[4:6]}-{day[6:]}T09:00:00",
        }
        yield PageResult([record], 1, 1, f"https://pncp.test/{day}/{modality}", {"data": [record]})


class EtlSmokeTests(unittest.TestCase):
    def test_repository_finds_opportunity_by_pncp_identity(self):
        connector = FakePNCPConnector()
        service = ETLSyncService(
            self.repository, connector, PNCPMapper()
        )
        service.sync(SyncRequest(
            endpoint="publicacao",
            filters={
                "date_from": "2026-08-01",
                "date_to": "2026-08-01",
                "modality_codes": [6],
            },
            fetch_details=True,
        ))

        detail = self.repository.get_opportunity_by_pncp_identity(
            "12345678000199", 2026, 1
        )

        self.assertIsNotNone(detail)
        self.assertEqual(len(detail["items"]), 2)
        first_item = detail["items"][0]
        self.assertEqual(
            first_item["description"],
            "Cadeira A - Assento estofado e base giratoria",
        )
        self.assertEqual(first_item["technical_object"], "Lote 1; Menor preco")

    def test_comprasgov_mapper_supports_flat_pncp_field_names(self):
        opportunity = ComprasGovMapper().map({
            "numeroControlePNCP": "00394452000103-1-014573/2026",
            "orgaoEntidadeCnpj": "00394452000103",
            "orgaoEntidadeRazaoSocial": "COMANDO DO EXERCITO",
            "anoCompraPncp": 2026,
            "sequencialCompraPncp": 14573,
            "numeroCompra": "88",
            "objetoCompra": "Treinamento",
            "modalidadeIdPncp": 9,
            "modalidadeNome": "Inexigibilidade",
            "situacaoCompraNomePncp": "Divulgada no PNCP",
            "unidadeOrgaoUfSigla": "RJ",
            "unidadeOrgaoMunicipioNome": "RIO DE JANEIRO",
            "unidadeOrgaoCodigoUnidade": "160307",
            "dataPublicacaoPncp": "2026-07-23T19:50:42",
            "dataAberturaPropostaPncp": "2026-07-24T08:00:00",
            "dataEncerramentoPropostaPncp": "2026-07-30T18:00:00",
        })

        self.assertEqual(opportunity.source_cnpj, "00394452000103")
        self.assertEqual(opportunity.buyer_cnpj, "00394452000103")
        self.assertEqual(opportunity.year, 2026)
        self.assertEqual(opportunity.sequence, 14573)
        self.assertEqual(opportunity.modality_code, 9)
        self.assertEqual(opportunity.uf, "RJ")
        self.assertEqual(opportunity.city, "RIO DE JANEIRO")
        self.assertEqual(opportunity.uasg, "160307")
        self.assertEqual(opportunity.status, "Divulgada no PNCP")
        self.assertEqual(opportunity.proposal_end_at, "2026-07-30T18:00:00")

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "etl.sqlite3"
        self.repository = ETLRepository(self.database_path)
        self.connector = FakePNCPConnector()
        self.service = ETLSyncService(self.repository, self.connector, PNCPMapper())

    def tearDown(self):
        self.temporary_directory.cleanup()

    def sync(self, dry_run=False):
        return self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            dry_run=dry_run,
            max_pages=1,
            max_records=10,
        ))

    def counts(self):
        connection = sqlite3.connect(self.database_path)
        try:
            return {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "etl_runs",
                    "source_records",
                    "opportunities",
                    "opportunity_items",
                    "opportunity_documents",
                    "opportunity_matches",
                )
            }
        finally:
            connection.close()

    def test_small_window_persists_raw_normalized_items_documents_and_match(self):
        result = self.sync()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(self.counts(), {
            "etl_runs": 1,
            "source_records": 1,
            "opportunities": 1,
            "opportunity_items": 2,
            "opportunity_documents": 1,
            "opportunity_matches": 1,
        })
        detail = self.repository.list_opportunities({"uf": "SP", "modality_code": 6})
        self.assertEqual(detail["total"], 1)
        opportunity = self.repository.get_opportunity(detail["items"][0]["id"])
        self.assertEqual(
            {(item["lot_number"], item["item_number"]) for item in opportunity["items"]},
            {("1", "1"), ("2", "1")},
        )
        first_item = opportunity["items"][0]
        self.assertEqual(first_item["description"], "Cadeira A - Assento estofado e base giratoria")
        self.assertEqual(first_item["granularity"], "lote_item")
        self.assertEqual(first_item["confidence"], 1.0)

    def test_unchanged_hash_is_skipped_but_raw_audit_is_preserved(self):
        self.sync()
        second = self.sync()

        self.assertEqual(second["skipped"], 1)
        self.assertEqual(self.counts()["opportunities"], 1)
        self.assertEqual(self.counts()["source_records"], 2)

    def test_changed_payload_updates_existing_opportunity(self):
        self.sync()
        self.connector.description = "Aquisicao atualizada de cadeiras"

        result = self.sync()

        self.assertEqual(result["updated"], 1)
        rows = self.repository.list_opportunities({"q": "atualizada"})
        self.assertEqual(rows["total"], 1)

    def test_listing_only_update_preserves_existing_items_and_documents(self):
        self.sync()
        self.connector.description = "Aquisicao atualizada sem detalhes"

        result = self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=10,
        ))

        self.assertEqual(result["updated"], 1)
        counts = self.counts()
        self.assertEqual(counts["opportunity_items"], 2)
        self.assertEqual(counts["opportunity_documents"], 1)

    def test_dry_run_records_run_without_loading_source_or_opportunity(self):
        result = self.sync(dry_run=True)

        self.assertEqual(result["status"], "dry_run")
        counts = self.counts()
        self.assertEqual(counts["etl_runs"], 1)
        self.assertEqual(counts["source_records"], 0)
        self.assertEqual(counts["opportunities"], 0)

    def test_internal_detail_uses_local_data_without_runtime_pncp_api(self):
        import server

        listing_service = ETLSyncService(self.repository, self.connector, PNCPMapper())
        listing_service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=1,
        ))
        opportunity_id = self.repository.list_opportunities()["items"][0]["id"]

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", return_value=self.connector),
            patch.object(server, "ALLOW_RUNTIME_PNCP_API", False),
            patch.object(server, "ALLOW_DETAIL_DOCUMENT_ON_DEMAND", False),
        ):
            detail = server.internal_opportunity_detail(opportunity_id)

        self.assertEqual(len(detail["itens"]), 0)
        self.assertEqual(len(detail["arquivos"]), 0)
        self.assertIn("banco local", detail["aviso_enriquecimento"])
        self.assertEqual(self.counts()["source_records"], 1)

    def test_internal_detail_enriches_documents_only_on_demand(self):
        import server

        listing_service = ETLSyncService(self.repository, self.connector, PNCPMapper())
        listing_service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=1,
        ))
        opportunity_id = self.repository.list_opportunities()["items"][0]["id"]

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", return_value=self.connector),
            patch.object(server, "ALLOW_DETAIL_DOCUMENT_ON_DEMAND", True),
        ):
            detail = server.internal_opportunity_detail(opportunity_id)

        self.assertEqual(len(detail["arquivos"]), 1)
        self.assertEqual(len(detail["itens"]), 0)
        self.assertIn("ETL completo", detail["aviso_enriquecimento"])
        counts = self.counts()
        self.assertEqual(counts["opportunity_documents"], 1)
        self.assertEqual(counts["opportunity_items"], 0)

    def test_bloco2_enriches_one_missing_opportunity_and_reuses_sqlite(self):
        import server

        listing_service = ETLSyncService(self.repository, self.connector, PNCPMapper())
        listing_service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=1,
        ))
        link = server.pncp_app_link("12345678000199", 2026, 1)

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", return_value=self.connector),
            patch.object(server, "IDENTIFICATION_CACHE", {}),
            patch.object(server, "ALLOW_BLOCO2_ON_DEMAND_ENRICHMENT", True),
        ):
            first = server.identify_items_from_pncp_link(link)

        self.assertEqual(first["count"], 2)
        self.assertEqual(first["cache_status"], "miss_enriched")
        self.assertEqual(first["items"][0]["descricao"], "Cadeira A - Assento estofado e base giratoria")
        self.assertEqual(self.counts()["source_records"], 2)
        self.assertEqual(self.counts()["opportunity_items"], 2)

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", side_effect=AssertionError("PNCP should not be called")),
            patch.object(server, "IDENTIFICATION_CACHE", {}),
            patch.object(server, "ALLOW_BLOCO2_ON_DEMAND_ENRICHMENT", True),
        ):
            second = server.identify_items_from_pncp_link(link)

        self.assertEqual(second["count"], 2)
        self.assertEqual(self.counts()["source_records"], 2)

    def test_comprasgov_reconciles_with_pncp_without_overwriting_canonical_record(self):
        self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=1,
        ))
        complementary = ETLSyncService(
            self.repository,
            FakeComprasGovConnector(),
            ComprasGovMapper(),
        )

        result = complementary.sync(SyncRequest(
            endpoint="/contratacoes",
            max_pages=1,
            max_records=1,
            fetch_details=False,
        ))

        self.assertEqual(result["skipped"], 1)
        row = self.repository.list_opportunities()["items"][0]
        self.assertEqual(row["source"], "pncp")
        self.assertEqual(row["description"], "Aquisicao de cadeiras")
        self.assertEqual(self.counts()["source_records"], 2)

    def test_html_rate_limit_response_is_reported_as_http_429(self):
        client = HttpJsonClient(
            retries=0,
            opener=lambda *_args, **_kwargs: FakeHttpResponse(
                "<html>Limite de Requisições Excedido</html>".encode("utf-8")
            ),
        )

        with self.assertRaisesRegex(ConnectorError, "HTTP 429"):
            client.get("https://pncp.test/consulta")


    def test_empty_response_is_reported_as_temporary_http_429(self):
        client = HttpJsonClient(
            retries=0,
            opener=lambda *_args, **_kwargs: FakeHttpResponse(b""),
        )

        with self.assertRaisesRegex(ConnectorError, "HTTP 429"):
            client.get("https://pncp.test/consulta")

    def test_generic_html_response_is_reported_as_temporary_http_429(self):
        client = HttpJsonClient(
            retries=0,
            opener=lambda *_args, **_kwargs: FakeHttpResponse(
                b"<html><body>Service temporarily unavailable</body></html>"
            ),
        )

        with self.assertRaisesRegex(ConnectorError, "HTTP 429"):
            client.get("https://pncp.test/consulta")


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "backfill.sqlite3"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_backfill_runs_each_day_and_modality_as_a_separate_checkpoint(self):
        connector = FakeBackfillConnector()

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-02",
            modality_codes=[1, 2],
            connector=connector,
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["completed"], 4)
        self.assertEqual(result["fetched"], 4)
        self.assertEqual(result["inserted"], 4)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM etl_runs WHERE run_type = 'backfill' AND status = 'success'"
                ).fetchone()[0],
                4,
            )
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0], 4)
        finally:
            connection.close()

    def test_backfill_accepts_current_modality_code_19(self):
        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-01",
            modality_codes=[19],
            connector=FakeBackfillConnector(),
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(result["completed"], 1)

    def test_comprasgov_bulk_backfill_uses_resumable_modality_checkpoints(self):
        connector = FakeComprasGovConnector()

        result = run_comprasgov_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-08-06",
            modality_codes=[1, 2],
            connector=connector,
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["completed"], 2)
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM backfill_checkpoints WHERE source = 'comprasgov' AND completed = 1"
                ).fetchone()[0],
                2,
            )
        finally:
            connection.close()

    def test_backfill_resume_skips_successful_compatible_checkpoints(self):
        first_connector = FakeBackfillConnector()
        arguments = {
            "date_from": "2026-04-01",
            "date_to": "2026-04-02",
            "modality_codes": [1],
            "unit_retries": 0,
            "delay": 0,
        }
        run_backfill(self.database_path, connector=first_connector, **arguments)
        resumed_connector = FakeBackfillConnector()

        result = run_backfill(self.database_path, connector=resumed_connector, **arguments)

        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["skipped"], 2)
        self.assertEqual(resumed_connector.calls, [])

    def test_backfill_can_group_dates_into_resumable_windows(self):
        connector = FakeBackfillConnector()

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-04",
            modality_codes=[1],
            connector=connector,
            window_days=2,
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(result["completed"], 2)
        self.assertEqual(result["window_days"], 2)
        self.assertEqual(connector.calls, [("20260401", 1), ("20260403", 1)])

    def test_smaller_windows_skip_ranges_covered_by_a_completed_broader_window(self):
        run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-30",
            modality_codes=[1],
            connector=FakeBackfillConnector(),
            window_days=30,
            unit_retries=0,
            delay=0,
        )
        weekly_connector = FakeBackfillConnector()

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-30",
            modality_codes=[1],
            connector=weekly_connector,
            window_days=7,
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(result["completed"], 0)
        self.assertEqual(result["skipped"], 5)
        self.assertEqual(weekly_connector.calls, [])

    def test_backfill_resumes_from_the_first_unfinished_page(self):
        class PagedConnector:
            SOURCE = "pncp"

            def __init__(self, fail_page=None):
                self.fail_page = fail_page
                self.calls = []

            def iter_endpoint(self, endpoint, filters, max_pages=None):
                start_page = int(filters.get("pagina") or 1)
                for page in range(start_page, 4):
                    self.calls.append(page)
                    if page == self.fail_page:
                        raise RuntimeError(f"failure on page {page}")
                    record = {
                        "numeroControlePNCP": f"12345678000199-1-00000{page}/2026",
                        "numeroCnpj": "12345678000199",
                        "anoCompra": 2026,
                        "sequencialCompra": page,
                        "numeroCompra": str(page),
                        "objetoCompra": f"Opportunity {page}",
                        "modalidadeId": 6,
                        "dataPublicacaoPncp": "2026-04-01T09:00:00",
                    }
                    yield PageResult(
                        [record], page, 3, f"https://pncp.test/publicacao?pagina={page}",
                        {"data": [record]},
                    )

        interrupted = PagedConnector(fail_page=3)
        first = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-30",
            modality_codes=[6],
            connector=interrupted,
            window_days=30,
            unit_retries=0,
            delay=0,
        )
        resumed = PagedConnector()
        second = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-30",
            modality_codes=[6],
            connector=resumed,
            window_days=30,
            unit_retries=0,
            delay=0,
        )

        self.assertEqual(first["status"], "partial")
        self.assertEqual(interrupted.calls, [1, 2, 3])
        self.assertEqual(second["completed"], 1)
        self.assertEqual(resumed.calls, [3])
        connection = sqlite3.connect(self.database_path)
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0], 3)
            checkpoint = connection.execute(
                "SELECT next_page, completed FROM backfill_checkpoints"
            ).fetchone()
            self.assertEqual(checkpoint, (4, 1))
        finally:
            connection.close()

    def test_backfill_continues_after_a_unit_exhausts_retries(self):
        connector = FakeBackfillConnector({("20260401", 1): 5})

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-02",
            modality_codes=[1],
            connector=connector,
            unit_retries=1,
            delay=0,
            retry_backoff=0,
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["completed"], 1)
        self.assertEqual(connector.calls.count(("20260401", 1)), 2)
        self.assertIn(("20260402", 1), connector.calls)
        connection = sqlite3.connect(self.database_path)
        try:
            statuses = connection.execute(
                "SELECT status, COUNT(*) FROM etl_runs GROUP BY status"
            ).fetchall()
            self.assertEqual(dict(statuses), {"failed": 2, "success": 1})
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0], 1)
        finally:
            connection.close()

    def test_backfill_can_defer_a_failed_unit_while_other_units_advance(self):
        connector = FakeBackfillConnector({("20260401", 1): 1})

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-01",
            modality_codes=[1, 2],
            connector=connector,
            unit_retries=1,
            defer_retries=True,
            delay=0,
            retry_backoff=0,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["completed"], 2)
        self.assertEqual(
            connector.calls,
            [("20260401", 1), ("20260401", 2), ("20260401", 1)],
        )

    def test_backfill_uses_longer_exponential_backoff_for_rate_limit(self):
        connector = FakeBackfillConnector({("20260401", 1): 2})
        waits = []

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-01",
            modality_codes=[1],
            connector=connector,
            unit_retries=2,
            delay=0,
            retry_backoff=3,
            rate_limit_backoff=20,
            sleeper=waits.append,
        )

        self.assertEqual(result["completed"], 1)
        self.assertEqual(waits, [3, 6])

    def test_backfill_detects_429_and_uses_rate_limit_backoff(self):
        class RateLimitedConnector(FakeBackfillConnector):
            def iter_endpoint(self, endpoint, filters, max_pages=None):
                self.calls.append((filters["dataInicial"], int(filters["codigoModalidadeContratacao"])))
                if len(self.calls) == 1:
                    raise RuntimeError("HTTP 429: Limite de Requisicoes Excedido")
                yield from super().iter_endpoint(endpoint, filters, max_pages)

        connector = RateLimitedConnector()
        waits = []

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-01",
            modality_codes=[1],
            connector=connector,
            unit_retries=1,
            delay=0,
            retry_backoff=3,
            rate_limit_backoff=20,
            sleeper=waits.append,
        )

        self.assertEqual(result["completed"], 1)
        self.assertEqual(waits, [20])

    def test_backfill_falls_back_to_open_proposals_when_publications_are_rate_limited(self):
        class EndpointFallbackConnector(FakeBackfillConnector):
            def __init__(self):
                super().__init__()
                self.endpoint_calls = []
                self.proposal_dates = []

            def iter_endpoint(self, endpoint, filters, max_pages=None):
                self.endpoint_calls.append(endpoint)
                if endpoint == "publicacao" and self.endpoint_calls.count("publicacao") == 1:
                    raise RuntimeError("HTTP 429: Too Many Requests")
                if endpoint == "proposta":
                    self.proposal_dates.append(filters["dataFinal"])
                    modality = int(filters["codigoModalidadeContratacao"])
                    record = {
                        "numeroControlePNCP": f"12345678000199-1-9999{modality:02d}/2026",
                        "numeroCnpj": "12345678000199",
                        "anoCompra": 2026,
                        "sequencialCompra": 999900 + modality,
                        "numeroCompra": f"open/{modality}",
                        "objetoCompra": f"Open opportunity {modality}",
                        "modalidadeId": modality,
                        "dataEncerramentoProposta": "2026-04-01T18:00:00",
                    }
                    yield PageResult(
                        [record],
                        1,
                        1,
                        f"https://pncp.test/proposta/{modality}",
                        {"data": [record]},
                    )
                    return
                yield from super().iter_endpoint(endpoint, filters, max_pages)

        connector = EndpointFallbackConnector()

        result = run_backfill(
            self.database_path,
            date_from="2026-04-01",
            date_to="2026-04-01",
            modality_codes=[1],
            connector=connector,
            unit_retries=1,
            delay=0,
            rate_limit_backoff=0,
            endpoint_cooldown=0,
            fallback_open_on_rate_limit=True,
            sleeper=lambda _seconds: None,
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["fallback_completed"], 1)
        self.assertEqual(result["endpoint_cooldowns"], 1)
        self.assertEqual(connector.endpoint_calls, ["publicacao", "proposta", "publicacao"])
        self.assertGreaterEqual(connector.proposal_dates[0], "2026-08-07")

if __name__ == "__main__":
    unittest.main()
