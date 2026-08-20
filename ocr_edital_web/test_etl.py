import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from etl import ComprasGovMapper, ETLRepository, ETLSyncService, PNCPMapper, SyncRequest
from etl.connectors import ConnectorError, HttpJsonClient
from etl.models import FetchedPayload, MatchResult, NormalizedOpportunity, OpportunityItem, PageResult
from etl.jobs import run_backfill, run_comprasgov_backfill
from scripts import enrich_missing_pncp_items


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

    def test_keyword_filter_is_accent_insensitive(self):
        self.connector.description = "Aquisição de cadeiras escolares"
        self.sync()

        without_accent = self.repository.list_opportunities({"keywords": ["aquisicao"]})
        with_accent = self.repository.list_opportunities({"keywords": ["aquisição"]})

        self.assertEqual(without_accent["total"], 1)
        self.assertEqual(with_accent["total"], 1)

    def test_object_type_uses_opportunity_text_without_requiring_items(self):
        self.connector.description = "Aquisição de mobiliário escolar"
        self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=10,
        ))

        materials = self.repository.list_opportunities({"object_type": "material"})
        services = self.repository.list_opportunities({"object_type": "servico"})

        self.assertEqual(materials["total"], 1)
        self.assertEqual(services["total"], 0)

    def test_object_type_keeps_unclassified_opportunities_visible(self):
        self.connector.description = "Edital escolar para atendimento da rede municipal"
        self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=10,
        ))

        materials = self.repository.list_opportunities({"object_type": "material"})
        services = self.repository.list_opportunities({"object_type": "servico"})

        self.assertEqual(materials["total"], 1)
        self.assertEqual(services["total"], 1)

    def test_object_type_rejects_a_known_opposite_type(self):
        self.connector.description = "Contratacao de empresa especializada para limpeza predial"
        self.service.sync(SyncRequest(
            endpoint="proposta",
            filters={"dataFinal": "20260806", "codigoModalidadeContratacao": 6},
            fetch_details=False,
            max_pages=1,
            max_records=10,
        ))

        materials = self.repository.list_opportunities({"object_type": "material"})
        services = self.repository.list_opportunities({"object_type": "servico"})

        self.assertEqual(materials["total"], 0)
        self.assertEqual(services["total"], 1)

    def test_missing_proposal_end_date_can_use_publication_window_explicitly(self):
        self.sync()
        with self.repository.connect() as connection, connection:
            connection.execute(
                "UPDATE opportunities SET proposal_end_at = NULL, published_at = ?",
                ("2026-08-05T09:00:00",),
            )

        hidden = self.repository.list_opportunities({
            "proposal_from": "2026-08-01T00:00:00",
            "proposal_to": "2026-08-10T23:59:59",
        })
        included = self.repository.list_opportunities({
            "proposal_from": "2026-08-01T00:00:00",
            "proposal_to": "2026-08-10T23:59:59",
            "include_missing_proposal_dates": True,
        })
        outside_publication_window = self.repository.list_opportunities({
            "proposal_from": "2026-08-06T00:00:00",
            "proposal_to": "2026-08-10T23:59:59",
            "include_missing_proposal_dates": True,
        })

        self.assertEqual(hidden["total"], 0)
        self.assertEqual(included["total"], 1)
        self.assertEqual(outside_publication_window["total"], 0)

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
            patch.object(server, "ALLOW_DETAIL_ITEMS_ON_DEMAND", False),
        ):
            detail = server.internal_opportunity_detail(opportunity_id)

        self.assertEqual(len(detail["itens"]), 0)
        self.assertEqual(len(detail["arquivos"]), 0)
        self.assertIn("banco local", detail["aviso_enriquecimento"])
        self.assertEqual(self.counts()["source_records"], 1)

    def test_internal_detail_enriches_missing_items_and_documents_once(self):
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
            patch.object(server, "ALLOW_DETAIL_ITEMS_ON_DEMAND", True),
        ):
            detail = server.internal_opportunity_detail(opportunity_id)

        self.assertEqual(len(detail["arquivos"]), 1)
        self.assertEqual(len(detail["itens"]), 2)
        self.assertEqual(detail["aviso_enriquecimento"], "")
        counts = self.counts()
        self.assertEqual(counts["opportunity_documents"], 1)
        self.assertEqual(counts["opportunity_items"], 2)
        self.assertEqual(counts["source_records"], 2)

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", side_effect=AssertionError("PNCP should not be called")),
            patch.object(server, "ALLOW_DETAIL_DOCUMENT_ON_DEMAND", True),
            patch.object(server, "ALLOW_DETAIL_ITEMS_ON_DEMAND", True),
        ):
            repeated = server.internal_opportunity_detail(opportunity_id)

        self.assertEqual(len(repeated["arquivos"]), 1)
        self.assertEqual(len(repeated["itens"]), 2)
        self.assertEqual(self.counts()["source_records"], 2)

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

class Bloco2ItemFlowTests(unittest.TestCase):
    CNPJ = "12345678000199"
    YEAR = 2026

    class ItemConnector:
        def __init__(self, payloads=None, error=None, delay=0):
            self.payloads = payloads or {}
            self.error = error
            self.delay = delay
            self.calls = []
            self.lock = threading.Lock()

        def iter_items(self, cnpj, year, sequence, max_pages=None):
            with self.lock:
                self.calls.append((cnpj, year, sequence, max_pages))
            if self.delay:
                time.sleep(self.delay)
            if self.error:
                raise self.error
            records = self.payloads.get(sequence, [])
            yield PageResult(
                records,
                1,
                1,
                f"https://pncp.test/{cnpj}/{year}/{sequence}/itens?pagina=1",
                {"data": records},
            )

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "bloco2.sqlite3"
        self.repository = ETLRepository(self.database_path)
        self.repository.initialize()
        for sequence in (1, 2):
            run_id = self.repository.create_run("pncp", "seed", {"sequence": sequence})
            opportunity = NormalizedOpportunity(
                external_key=f"{self.CNPJ}-1-{sequence:06d}/{self.YEAR}",
                source="pncp",
                title=f"Edital {sequence}",
                source_cnpj=self.CNPJ,
                buyer_cnpj=self.CNPJ,
                year=self.YEAR,
                sequence=sequence,
                detail_url=f"https://pncp.gov.br/app/editais/{self.CNPJ}/{self.YEAR}/{sequence}",
            )
            self.repository.persist_record(
                run_id=run_id,
                source_endpoint="seed",
                request_url="https://pncp.test/seed",
                raw_payload={"sequence": sequence},
                opportunity=opportunity,
                match=MatchResult(),
            )
            self.repository.finish_run(
                run_id,
                status="success",
                counters={"fetched": 1, "inserted": 1, "updated": 0, "skipped": 0, "failed": 0},
            )

    def tearDown(self):
        self.temporary_directory.cleanup()

    def link(self, sequence):
        return f"https://pncp.gov.br/app/editais/{self.CNPJ}/{self.YEAR}/{sequence}"

    def opportunity_id(self, sequence):
        return self.repository.get_opportunity_by_pncp_identity(
            self.CNPJ, self.YEAR, sequence
        )["opportunity"]["id"]

    def item_count(self, sequence):
        with self.repository.connect() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM opportunity_items WHERE opportunity_id = ?",
                (self.opportunity_id(sequence),),
            ).fetchone()[0]

    def audit_rows(self, sequence):
        with self.repository.connect() as connection:
            return connection.execute(
                """
                SELECT s.status, s.raw_payload_json, s.error_message, r.status run_status
                FROM source_records s
                JOIN etl_runs r ON r.id = s.etl_run_id
                WHERE s.source_endpoint = 'opportunity_item_enrichment'
                  AND s.opportunity_id = ?
                ORDER BY s.created_at, s.id
                """,
                (self.opportunity_id(sequence),),
            ).fetchall()

    @staticmethod
    def valid_item(number="1", description="Cadeira local", **overrides):
        payload = {
            "numeroLote": "1",
            "numeroItem": number,
            "descricao": description,
            "quantidade": 0,
            "unidadeMedida": None,
            "valorUnitarioEstimado": 0,
        }
        payload.update(overrides)
        return payload

    def call(self, sequence, connector, cache=None):
        import server

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", return_value=connector),
            patch.object(server, "IDENTIFICATION_CACHE", cache if cache is not None else {}),
            patch.object(server, "ALLOW_BLOCO2_ON_DEMAND_ENRICHMENT", True),
        ):
            return server.identify_items_from_pncp_link(self.link(sequence))

    def test_existing_items_use_only_sqlite_and_preserve_optional_values(self):
        import server

        self.repository.replace_opportunity_items(
            self.opportunity_id(1),
            [OpportunityItem(
                source_item_id="local-1",
                item_number="1",
                lot_number="1",
                title="Cadeira local",
                description="Cadeira local completa",
                quantity=0,
                unit=None,
                estimated_unit_value=0,
                estimated_total_value=None,
            )],
        )
        connector = self.ItemConnector(error=AssertionError("PNCP nao deveria ser chamado"))

        result = self.call(1, connector)

        self.assertEqual(connector.calls, [])
        self.assertEqual(result["source"], "opportunity_items")
        self.assertEqual(result["items"][0]["quantidade"], "0")
        self.assertIsNone(result["items"][0]["unidade"])
        self.assertEqual(result["items"][0]["valor_unitario_estimado"], 0)
        self.assertIsNone(result["items"][0]["valor_total_estimado"])
        self.assertFalse(result["pncp_items_check"]["api_available"])

    def test_missing_items_fetch_once_persist_audit_reload_and_then_stay_local(self):
        connector = self.ItemConnector({1: [self.valid_item(description="Item PNCP")]})

        first = self.call(1, connector)

        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(first["source"], "opportunity_items_enriquecido_bloco2")
        self.assertEqual(first["items"][0]["descricao"], "Item PNCP")
        self.assertEqual(self.item_count(1), 1)
        audit = self.audit_rows(1)
        self.assertEqual([(row["status"], row["run_status"]) for row in audit], [("success", "success")])
        self.assertNotIn("Item PNCP", audit[0]["raw_payload_json"])
        self.assertIn('"items_received":1', audit[0]["raw_payload_json"])

        second_connector = self.ItemConnector(error=AssertionError("PNCP nao deveria ser chamado novamente"))
        second = self.call(1, second_connector, cache={})
        self.assertEqual(second_connector.calls, [])
        self.assertEqual(second["items"], first["items"])
        self.assertEqual(self.item_count(1), 1)

    def test_pncp_failure_is_audited_and_retry_succeeds_without_duplicates(self):
        failing = self.ItemConnector(error=ConnectorError("temporary PNCP failure internal detail"))

        with self.assertRaisesRegex(RuntimeError, "continuam pendentes") as raised:
            self.call(1, failing)

        self.assertNotIn("internal detail", str(raised.exception))
        self.assertEqual(self.item_count(1), 0)
        self.assertEqual(self.audit_rows(1)[0]["status"], "failed")

        working = self.ItemConnector({1: [self.valid_item(description="Item apos retry")]})
        result = self.call(1, working)
        self.assertEqual(result["items"][0]["descricao"], "Item apos retry")
        self.assertEqual(self.item_count(1), 1)

        repeated = self.call(1, self.ItemConnector(error=AssertionError("sem nova chamada")), cache={})
        self.assertEqual(repeated["count"], 1)
        self.assertEqual(self.item_count(1), 1)

    def test_invalid_link_stops_before_connector_creation(self):
        import server

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector") as connector,
            self.assertRaisesRegex(ValueError, "Link PNCP inv"),
        ):
            server.identify_items_from_pncp_link("https://example.com/app/editais/1")
        connector.assert_not_called()

    def test_empty_or_malformed_response_does_not_persist_or_complete(self):
        cases = (
            (1, []),
            (2, [{"numeroItem": "1", "quantidade": 3}]),
        )
        for sequence, records in cases:
            with self.subTest(sequence=sequence):
                connector = self.ItemConnector({sequence: records})
                with self.assertRaisesRegex(RuntimeError, "continuam pendentes"):
                    self.call(sequence, connector)
                self.assertEqual(self.item_count(sequence), 0)
                audit = self.audit_rows(sequence)
                self.assertEqual(audit[-1]["status"], "failed")
                self.assertEqual(audit[-1]["run_status"], "failed")

    def test_partial_insert_failure_rolls_back_every_item(self):
        original_insert = ETLRepository._insert_items

        def fail_after_first(connection, opportunity_id, items, now):
            original_insert(connection, opportunity_id, items[:1], now)
            raise sqlite3.OperationalError("simulated write failure")

        connector = self.ItemConnector({1: [
            self.valid_item("1", "Primeiro"),
            self.valid_item("2", "Segundo"),
        ]})
        with patch.object(ETLRepository, "_insert_items", side_effect=fail_after_first):
            with self.assertRaisesRegex(RuntimeError, "continuam pendentes"):
                self.call(1, connector)

        self.assertEqual(self.item_count(1), 0)
        self.assertEqual(self.audit_rows(1)[-1]["status"], "failed")

    def test_different_opportunities_never_mix_items(self):
        connector = self.ItemConnector({
            1: [self.valid_item("1", "Item da oportunidade um", numeroLote="A")],
            2: [self.valid_item("1", "Item da oportunidade dois", numeroLote="B")],
        })

        first = self.call(1, connector)
        second = self.call(2, connector)

        self.assertEqual(first["items"][0]["lote"], "A")
        self.assertEqual(second["items"][0]["lote"], "B")
        self.assertNotEqual(self.opportunity_id(1), self.opportunity_id(2))
        with self.repository.connect() as connection:
            descriptions = {
                row["opportunity_id"]: row["description"]
                for row in connection.execute(
                    "SELECT opportunity_id, description FROM opportunity_items"
                )
            }
        self.assertEqual(descriptions[self.opportunity_id(1)], "Item da oportunidade um")
        self.assertEqual(descriptions[self.opportunity_id(2)], "Item da oportunidade dois")

    def test_empty_or_invalid_cache_falls_through_to_sqlite_or_pncp(self):
        import server

        self.repository.replace_opportunity_items(
            self.opportunity_id(1),
            [OpportunityItem("local", "1", "Item local", description="Item local")],
        )
        local_cache = {}
        server.cache_set(local_cache, self.link(1), {"items": []})
        local = self.call(
            1,
            self.ItemConnector(error=AssertionError("cache invalido deve cair no SQLite")),
            cache=local_cache,
        )
        self.assertEqual(local["items"][0]["descricao"], "Item local")

        missing_cache = {}
        server.cache_set(missing_cache, self.link(2), {
            "source": "opportunity_items",
            "items": [{"item": "1", "descricao": "identidade errada"}],
            "pncp": {"cnpj": "00000000000000", "ano": self.YEAR, "sequencial": 2},
        })
        remote = self.call(
            2,
            self.ItemConnector({2: [self.valid_item(description="Item correto")]}),
            cache=missing_cache,
        )
        self.assertEqual(remote["items"][0]["descricao"], "Item correto")

    def test_concurrent_requests_fetch_the_same_opportunity_only_once(self):
        import server

        connector = self.ItemConnector(
            {1: [self.valid_item(description="Item concorrente")]},
            delay=0.08,
        )
        results = []
        errors = []
        cache = {}

        def worker():
            try:
                results.append(server.identify_items_from_pncp_link(self.link(1)))
            except Exception as exc:
                errors.append(exc)

        with (
            patch.object(server, "DATABASE_PATH", self.database_path),
            patch.object(server, "PNCPConnector", return_value=connector),
            patch.object(server, "IDENTIFICATION_CACHE", cache),
            patch.object(server, "ALLOW_BLOCO2_ON_DEMAND_ENRICHMENT", True),
        ):
            threads = [threading.Thread(target=worker) for _ in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 5)
        self.assertEqual(len(connector.calls), 1)
        self.assertEqual(self.item_count(1), 1)


class BatchItemEnrichmentTests(unittest.TestCase):
    def test_batch_enrichment_calls_only_item_endpoint_and_uses_atomic_persistence(self):
        persisted = []

        class Repository:
            def persist_opportunity_items_enrichment(self, **kwargs):
                persisted.append(kwargs)
                return {"persisted": True, "count": len(kwargs["items"])}

        class Connector:
            def iter_items(self, cnpj, year, sequence, max_pages):
                self.identity = (cnpj, year, sequence, max_pages)
                yield PageResult(
                    records=[{
                        "numeroItem": 1,
                        "descricao": "Cadeira escolar completa",
                        "quantidade": 20,
                        "unidadeMedida": "UN",
                    }],
                    page_number=1,
                    total_pages=1,
                    request_url="https://pncp.test/itens?pagina=1",
                    raw_payload={"data": []},
                )

            def fetch_detail(self, *_args):
                raise AssertionError("detalhes não devem ser consultados")

            def fetch_documents(self, *_args):
                raise AssertionError("documentos não devem ser consultados")

        row = {
            "id": "opportunity-1",
            "external_key": "12345678000199-1-000001/2026",
            "source_cnpj": "12345678000199",
            "year": 2026,
            "sequence": 1,
            "detail_url": "https://pncp.gov.br/app/editais/12345678000199/2026/1",
        }
        connector = Connector()

        result = enrich_missing_pncp_items._enrich_one(
            repository=Repository(),
            connector=connector,
            mapper=PNCPMapper(),
            run_id="run-1",
            row=row,
            item_max_pages=20,
            dry_run=False,
        )

        self.assertEqual(result, ("updated", 1, 0, []))
        self.assertEqual(connector.identity, ("12345678000199", 2026, 1, 20))
        self.assertFalse(persisted[0]["finish_run"])
        self.assertEqual(persisted[0]["audit_summary"]["mode"], "items_only_batch")


if __name__ == "__main__":
    unittest.main()
