import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from catalog_library import LIBRARY, find_catalog_references, library_index, library_summary
from catalog_rules import analyze_catalog_item
from catalog_generator import write_audit_json


class CatalogLibraryTests(unittest.TestCase):
    def test_original_documents_are_searchable_with_locations(self):
        manifest, _, _ = library_index()
        self.assertEqual(len(manifest['products']), 37)
        self.assertEqual(library_summary()['searchable_reports'], 164)
        documents = manifest['documents']
        self.assertTrue(any(d['format'] == '.pdf' and d['text'] and d['locations'][0].get('page') for d in documents))
        for doc in documents:
            if 'pedido no edital' in doc['source'].lower() or doc['source'].endswith('Edital pinhais.pdf'):
                self.assertEqual(doc['kind'], 'requisito_edital')
    def test_manifest_is_deduplicated_and_has_only_reference_formats(self):
        manifest, _, _ = library_index()
        docs = manifest['documents']
        self.assertEqual(len({d['sha256'] for d in docs}), len(docs))
        self.assertEqual(library_summary()['documents'], 174)
        for doc in docs:
            self.assertIn(doc['format'], {'.md', '.txt', '.pdf', '.docx'})
            self.assertNotIn('node_modules', doc['source'])
            self.assertNotIn('AGENTS.md', doc['source'])

    def test_text_hashes_match_imported_content(self):
        for doc in library_index()[0]['documents']:
            if doc['format'] in {'.md', '.txt'}:
                # Original bytes may include a UTF-8 BOM, so preserve that check separately.
                raw_hash = hashlib.sha256(doc['text'].encode('utf-8')).hexdigest()
                bom_hash = hashlib.sha256(b'\xef\xbb\xbf' + doc['text'].encode('utf-8')).hexdigest()
                self.assertIn(doc['sha256'], {raw_hash, bom_hash})

    def test_retrieves_upholstery_evidence_without_tender_sources(self):
        rows = find_catalog_references('Cadeira revestimento tecido poliester gramatura tracao urdume')
        self.assertTrue(rows)
        self.assertTrue(any('revestimento-tecido' in row['fonte'] for row in rows))
        self.assertTrue(all(row['tipo'] != 'requisito_edital' for row in rows))
        self.assertTrue(all(row['estado'] == 'referencia_para_revisao' for row in rows))

    def test_unrelated_product_does_not_match_shared_material(self):
        self.assertEqual(find_catalog_references('Veiculo automotor espuma tecido poliester'), [])
        self.assertEqual(find_catalog_references('Cadeira'), [])

    def test_candidates_do_not_create_a_model_or_publish_claims(self):
        result = analyze_catalog_item({'produto': 'Mocho bipartido', 'descricao': 'Mocho ergonomico bipartido estofado'})
        self.assertTrue(result['referencias_complementares'])
        self.assertEqual(result['status_catalogo'], 'bloqueado_sem_modelo')
        self.assertEqual(result['caracteristicas_catalogo'], [])
        self.assertFalse(result['analise_aderencia']['declaracao_atendimento_automatica'])

    def test_results_are_independent_and_recomputed(self):
        text = 'Cadeira tecido poliester gramatura tracao'
        first = find_catalog_references(text)
        first[0]['fonte'] = 'changed'
        self.assertNotEqual(find_catalog_references(text)[0]['fonte'], 'changed')
        result = analyze_catalog_item({'produto': 'Veiculo', 'descricao': 'Automovel', 'referencias_complementares': first})
        self.assertEqual(result['referencias_complementares'], [])

    def test_audit_export_contains_traceable_references(self):
        item = analyze_catalog_item({'produto': 'Mocho bipartido', 'descricao': 'Mocho ergonomico bipartido estofado'})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.json'
            write_audit_json(path, {}, [item], [])
            saved = json.loads(path.read_text(encoding='utf-8'))
            refs = saved['auditoria_oportunidade']['itens'][0]['referencias_complementares']
            self.assertTrue(refs)
            self.assertTrue(all(len(row['sha256']) == 64 for row in refs))


if __name__ == '__main__':
    unittest.main()
