"""Block 7 regressions for reference selection and document availability."""
import math
import unittest
from unittest.mock import patch

import catalog_library as library
import server


def legacy_references(text):
    query = library.tokens(text)
    _, entries, frequency = library.library_index()
    matches = []
    for row, words, title in entries:
        shared = query & words
        if len(shared) < 2:
            continue
        score = sum(math.log(1 + len(entries) / frequency[word]) * (3 if word in title else 1) for word in shared)
        locations = row.get("locations") or [{"text": row["text"]}]
        location = max(locations, key=lambda entry: len(library.tokens(entry["text"]) & shared))
        lines = [line.strip() for line in location["text"].splitlines() if line.strip() and not line.startswith("#")]
        excerpt = max(lines, key=lambda line: len(library.tokens(line) & shared), default="")
        matches.append((score, row["source"], (row["id"], excerpt[:900], location.get("page"), location.get("section"))))
    matches.sort(key=lambda entry: (-entry[0], entry[1]))
    return [entry[2] for entry in matches[:5]]


class CatalogAuditTests(unittest.TestCase):
    def test_optimized_reference_ids_order_excerpts_and_locations_are_unchanged(self):
        for text in (
            "Cadeira giratoria mesh espuma injetada poliuretano pistao classe 4",
            "Mocho ergonomico bipartido estofado",
            "Cadeira fixa longarina tubo aco pintura solda MIG",
            "Cadeira tecido poliester gramatura tracao urdume",
            "Cadeira polipropileno concha plastica empilhavel ABNT",
        ):
            with self.subTest(text=text):
                actual = library.find_catalog_references(text)
                self.assertEqual([(row["id"], row["trecho"], row["pagina"], row["secao"]) for row in actual], legacy_references(text))

    def test_only_top_five_documents_have_their_locations_scanned(self):
        library._find_references.cache_clear()
        with patch.object(library, "_reference_locations", wraps=library._reference_locations) as locations:
            rows = library.find_catalog_references("Cadeira giratoria mesh poliuretano espuma revestimento tecido pistao 999")
        self.assertEqual(locations.call_count, len(rows))
        self.assertLessEqual(locations.call_count, 5)

    def test_download_failure_is_not_reported_as_no_documents_published(self):
        for errors in ([], ["Edital.pdf: timeout ao baixar"]):
            job_id = "e" * 32
            with (
                self.subTest(errors=errors),
                patch.dict(server.CATALOG_GENERATOR_JOBS, {job_id: {"id": job_id}}, clear=True),
                patch.object(server, "CATALOG_GENERATOR_PERSISTED_IDS", set()),
                patch.object(server, "pncp_purchase_metadata", return_value={}),
                patch.object(server, "identify_items_from_pncp_link", return_value={"items": [
                    {"item": "1", "descricao": "Cadeira fixa", "quantidade": "2", "unidade": "UN"}
                ]}),
                patch.object(server, "catalog_generator_document_candidates", return_value=([], errors)),
                patch.object(server, "saved_catalog_repertoire", side_effect=lambda items: items),
            ):
                server.run_catalog_generator_job(job_id, "https://pncp.gov.br/app/editais/01612836000100/2026/101")
                job = server.catalog_generator_job(job_id)
                self.assertEqual(job["status"], "ready")
                warnings = job["result"]["warnings"]
                empty_message = "Nenhum documento oficial foi disponibilizado pelo PNCP."
                self.assertEqual(empty_message in warnings, not errors)
                if errors:
                    self.assertIn(errors[0], warnings)


if __name__ == "__main__":
    unittest.main()
