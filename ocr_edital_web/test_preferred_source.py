import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import server
from etl.connectors import ConnectorError
from etl.models import FetchedPayload, PageResult
from etl.repository import ETLRepository
from etl.preferred_source import (
    BASE, DETAIL, ITEMS, PURCHASES, ComprasGovSource,
    PreferredProcurementConnector, control_number,
    canonical_purchase,
)


CNPJ = "12345678000199"
IDENTITY = (CNPJ, 2026, 7)
CONTROL = control_number(*IDENTITY)


def envelope(rows, remaining=0, total=None, pages=1):
    return {"resultado": rows, "totalRegistros": len(rows) if total is None else total,
            "totalPaginas": pages, "paginasRestantes": remaining}


def purchase():
    return {"numeroControlePNCP": CONTROL, "orgaoEntidadeCnpj": CNPJ,
            "anoCompraPncp": 2026, "sequencialCompraPncp": 7,
            "objetoCompra": "Cadeiras", "modalidadeIdPncp": 6,
            "dataPublicacaoPncp": "2026-09-09", "unidadeOrgaoUfSigla": "SP"}


def item():
    return {"numeroControlePNCPCompra": CONTROL, "numeroItemPncp": 1,
            "descricaoResumida": "Cadeira", "descricaodetalhada": "Cadeira de madeira com bracos",
            "numeroGrupo": 0, "quantidade": 2, "unidadeMedida": "UN",
            "valorUnitarioEstimado": 10, "valorTotal": 20}


class PreferredSourceTests(unittest.TestCase):
    def setUp(self):
        ComprasGovSource._cooldowns.clear()
        self.client = Mock()
        self.primary = ComprasGovSource(self.client)
        self.fallback = Mock()
        self.connector = PreferredProcurementConnector(primary=self.primary, fallback=self.fallback)

    def reply(self, endpoint, payload):
        self.client.get.return_value = FetchedPayload(payload, BASE + endpoint)

    def test_detail_prefers_comprasgov_and_maps_fields(self):
        self.reply(DETAIL, envelope([purchase()]))
        result = self.connector.fetch_detail(*IDENTITY)
        self.assertEqual(result.payload["orgaoEntidade"]["cnpj"], CNPJ)
        self.assertEqual(result.payload["anoCompra"], 2026)
        self.assertEqual(result.request_url, BASE + DETAIL)
        self.fallback.fetch_detail.assert_not_called()
        self.client.get.assert_called_once_with(BASE + DETAIL, {"tipo": "numeroControlePNCPCompra", "codigo": CONTROL})

    def test_items_keep_detailed_description_and_numbers(self):
        self.reply(ITEMS, envelope([item()]))
        result = list(self.connector.iter_items(*IDENTITY, 20))
        self.assertEqual(result[0].records[0]["descricao"], item()["descricaodetalhada"])
        self.assertEqual(result[0].records[0]["numeroItem"], 1)
        self.assertEqual(result[0].records[0]["numeroGrupo"], "")
        self.fallback.iter_items.assert_not_called()

    def test_invalid_empty_partial_duplicate_or_wrong_identity_falls_back(self):
        bad_item = {**item(), "numeroControlePNCPCompra": "wrong"}
        for payload in (envelope([]), envelope([item()], total=2),
                        envelope([item()], remaining=1), envelope([bad_item]),
                        envelope([item(), item()]), {"message": "timeout"},
                        envelope([{**item(), "descricaodetalhada": "", "descricaoResumida": ""}])):
            with self.subTest(payload=payload):
                ComprasGovSource._cooldowns.clear()
                self.reply(ITEMS, payload)
                self.fallback.iter_items.return_value = ["pncp-page"]
                self.assertEqual(list(self.connector.iter_items(*IDENTITY, 20)), ["pncp-page"])
        self.assertEqual(self.fallback.iter_items.call_count, 7)

    def test_timeout_cooldown_is_per_endpoint(self):
        self.client.get.side_effect = [TimeoutError("timeout"), FetchedPayload(envelope([item()]), BASE + ITEMS)]
        self.connector.fetch_detail(*IDENTITY)
        self.connector.fetch_detail(*IDENTITY)
        self.assertEqual(self.client.get.call_count, 1)
        self.assertEqual(self.fallback.fetch_detail.call_count, 2)
        self.assertEqual(len(list(self.connector.iter_items(*IDENTITY))), 1)
        self.assertEqual(self.client.get.call_count, 2)

    def test_both_sources_fail_error_is_not_empty_success(self):
        self.client.get.side_effect = TimeoutError()
        self.fallback.fetch_detail.side_effect = ConnectorError("PNCP falhou")
        with self.assertRaisesRegex(ConnectorError, "PNCP falhou"):
            self.connector.fetch_detail(*IDENTITY)

    def test_documents_use_pncp_without_nonexistent_comprasgov_endpoint(self):
        self.connector.fetch_documents(*IDENTITY)
        self.client.get.assert_not_called()
        self.fallback.fetch_documents.assert_called_once_with(*IDENTITY)

    def test_publication_pagination_does_not_stop_on_short_page(self):
        other = {**purchase(), "numeroControlePNCP": control_number(CNPJ, 2026, 8)}
        self.client.get.side_effect = [
            FetchedPayload(envelope([purchase()], remaining=1, total=2, pages=2), BASE + PURCHASES),
            FetchedPayload(envelope([other], total=2, pages=2), BASE + PURCHASES),
        ]
        pages = list(self.primary.iter_publications({"codigoModalidade": 6}))
        self.assertEqual(len(pages), 2)
        self.assertEqual(self.client.get.call_args_list[1].args[1]["pagina"], 2)

    def test_publication_page_failure_discards_primary_before_fallback(self):
        self.client.get.side_effect = [
            FetchedPayload(envelope([purchase()], remaining=1, total=2, pages=2), BASE + PURCHASES),
            TimeoutError(),
        ]
        self.fallback.iter_endpoint.return_value = ["pncp-page"]
        rows = list(self.connector.iter_endpoint("publicacao", {
            "dataInicial": "20260909", "dataFinal": "20260909", "codigoModalidadeContratacao": 6,
        }, 2))
        self.assertEqual(rows, ["pncp-page"])

    def test_publication_translates_modality_not_same_numeric_code(self):
        self.reply(PURCHASES, envelope([purchase()]))
        pages = list(self.connector.iter_endpoint("publicacao", {
            "dataInicial": "20260909", "dataFinal": "20260909", "codigoModalidadeContratacao": 6,
        }, 2))
        self.assertEqual(len(pages), 1)
        self.assertEqual(self.client.get.call_args.args[1]["codigoModalidade"], 5)
        self.assertEqual(self.client.get.call_args.args[1]["dataPublicacaoPncpInicial"], "2026-09-09")
        self.fallback.iter_endpoint.assert_not_called()

    def test_unsupported_modality_and_date_use_pncp(self):
        self.fallback.iter_endpoint.return_value = ["pncp-page"]
        for endpoint, modality in (("publicacao", 12), ("proposta", 6), ("atualizacao", 6)):
            self.assertEqual(list(self.connector.iter_endpoint(endpoint, {
                "dataInicial": "20260909", "dataFinal": "20260909", "codigoModalidadeContratacao": modality,
            }, 2)), ["pncp-page"])
        self.client.get.assert_not_called()

    def test_search_imports_and_filters_in_temporary_database(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = ETLRepository(Path(directory) / "test.sqlite3")
            repository.initialize()
            page = PageResult([canonical_purchase(purchase())], 1, 1, BASE + PURCHASES, envelope([purchase()]))
            with patch.object(server, "etl_repository", return_value=repository), \
                 patch.object(server, "ComprasGovSource") as source:
                source.return_value.iter_publications.return_value = [page]
                params = {"dataInicial": "20260909", "dataFinal": "20260909", "campoData": "publicacao",
                          "codigoModalidadeContratacao": "6", "uf": "SP"}
                result = server.search_online_bids(params)
                self.assertEqual(result["total"], 1)
                self.assertEqual(result["reconciliation"]["inserted"], 1)
                self.assertEqual(result["results"][0]["cnpj"], CNPJ)
                server.search_online_bids(params)
                self.assertEqual(server.internal_opportunities_response(params)["total"], 1)
                detail = repository.get_opportunity_by_pncp_identity(*IDENTITY)
                self.assertEqual(detail["opportunity"]["description"], "Cadeiras")
                source.return_value.iter_publications.assert_called_with({
                    "dataPublicacaoPncpInicial": "2026-09-09", "dataPublicacaoPncpFinal": "2026-09-09",
                    "codigoModalidade": 5, "unidadeOrgaoUfSigla": "SP", "unidadeOrgaoCodigoUnidade": None,
                })

    def test_closing_search_never_claims_publication_coverage_as_complete(self):
        repository = Mock()
        repository.persist_record.return_value = ("inserted", 1)
        page = PageResult([canonical_purchase(purchase())], 1, 1, BASE + PURCHASES, {})
        with patch.object(server, "etl_repository", return_value=repository), \
             patch.object(server, "ComprasGovSource") as source:
            source.return_value.iter_publications.return_value = [page]
            result = server.refresh_comprasgov_search({"campoData": "encerramento", "codigoModalidadeContratacao": "6"})
            self.assertIn("abertura/encerramento", result["fallback_reason"])

    def test_local_item_hit_does_not_call_online(self):
        with patch.object(server, "identify_items_from_opportunity_store", return_value={"items": [
            {"item": "1", "descricao": "Cadeira", "quantidade": "2", "valor_unitario_estimado": 10},
        ]}), patch.object(server, "ComprasGovSource") as primary, patch.object(server, "request_json") as pncp:
            self.assertEqual(server.list_pncp_item_payload(*IDENTITY)[0]["valorUnitarioEstimado"], 10)
            primary.assert_not_called()
            pncp.assert_not_called()

    def test_search_success_does_not_call_pncp(self):
        with patch.object(server, "refresh_comprasgov_search", return_value={"fallback_reason": "", "inserted": 3}), \
             patch.object(server, "internal_opportunities_response", return_value={"results": [], "total": 3}), \
             patch.object(server, "search_pncp_open_bids") as fallback:
            result = server.search_online_bids({})
            self.assertEqual(result["provider_attempts"], ["comprasgov"])
            fallback.assert_not_called()

    def test_search_fallback_keeps_import_counts(self):
        with patch.object(server, "refresh_comprasgov_search", return_value={"fallback_reason": "timeout", "inserted": 3}), \
             patch.object(server, "search_pncp_open_bids", return_value={"complete": True, "reconciliation": {"inserted": 2}}) as fallback:
            result = server.search_online_bids({})
            self.assertEqual(result["provider_attempts"], ["comprasgov", "pncp"])
            self.assertEqual(result["reconciliation"]["inserted"], 5)
            fallback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
