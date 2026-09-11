import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from importar_comprasgov import normalize, simulate, DATE_FIELDS, select_candidate, plan_gaps, DuplicateConflict
from importar_comprasgov import apply_import


def example():
    return dict(numero_controle_pncp='00394494010441-1-000089/2026',
                orgao_entidade_cnpj=394494010441, sequencial_compra_pncp=89,
                ano_compra_pncp=2026, modalidade_id_pncp=6, codigo_modalidade=5,
                ind_atual=1, contratacao_excluida=0, id_compra='20010905900032026',
                data_atualizacao_pncp='2026-02-27 07:02:10', valor_total_estimado='0',
                unidade_orgao_codigo_unidade=200109, numero_compra=90003,
                link_sistema_origem='https://example.org/?compra=20010905900032026',
                objeto_compra='Compra de cadeiras', orgao_entidade_razao_social='Orgao teste',
                **{v: '' for v in [*DATE_FIELDS.values(), 'processo', 'unidade_orgao_uf_sigla',
                                    'unidade_orgao_municipio_nome', 'modalidade_nome', 'situacao_compra_nome_pncp']})


class ImportTest(unittest.TestCase):
    def test_double_quotes_preferred_without_rewriting_apostrophes(self):
        single = example() | {'objeto_compra': "Caixa d'agua modelo 'A'"}
        double = example() | {'objeto_compra': 'Caixa d\'agua modelo "A"'}
        for rows in ([single, double], [double, single]):
            data, warnings = select_candidate(rows)
            self.assertEqual(data['description'], double['objeto_compra'])
            self.assertTrue(any('aspas duplas' in w for w in warnings))
        data, _ = select_candidate([single])
        self.assertEqual(data['description'], single['objeto_compra'])

    def test_quote_equivalence_does_not_hide_actual_conflicts(self):
        for field, first, second in (
            ('objeto_compra', 'Modelo "A"', "Modelo 'B'"),
            ('objeto_compra', 'Tamanho "3"', "Tamanho '6'"),
            ('processo', '"123"', "'123'"),
        ):
            with self.subTest(field=field), self.assertRaises(DuplicateConflict):
                select_candidate([example() | {field: first}, example() | {field: second}])

    def test_apply_backup_idempotency_and_rollback(self):
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'db.sqlite'
                row = example()
                data, _ = normalize(row)
                columns = set(data) | {'id', 'created_at', 'updated_at', 'record_hash'}
                with sqlite3.connect(path) as db:
                    db.execute('CREATE TABLE staging (' + ','.join('"'+k+'" TEXT' for k in row) + ')')
                    db.execute('INSERT INTO staging VALUES (' + ','.join('?' for _ in row) + ')', tuple(row.values()))
                    db.execute('CREATE TABLE opportunities (' + ','.join('"'+k+'" TEXT' for k in columns) + ')')
                    if fail:
                        db.execute("CREATE TRIGGER reject_insert AFTER INSERT ON opportunities BEGIN SELECT RAISE(ABORT, 'test failure'); END")
                db.close()
                if fail:
                    with self.assertRaises(sqlite3.IntegrityError):
                        apply_import(path, 'staging', Path(directory)/'reports')
                    with sqlite3.connect(path) as db:
                        self.assertEqual(db.execute('SELECT count(*) FROM opportunities').fetchone()[0], 0)
                    db.close()
                else:
                    result, _ = apply_import(path, 'staging', Path(directory)/'reports')
                    self.assertEqual(result['contagens']['inserir'], 1)
                    with sqlite3.connect(result['backup']) as backup:
                        self.assertEqual(backup.execute('SELECT count(*) FROM opportunities').fetchone()[0], 0)
                    backup.close()
                    result, _ = apply_import(path, 'staging', Path(directory)/'reports')
                    self.assertEqual(result['contagens'].get('inserir', 0), 0)
                    self.assertEqual(result['depois'], 1)

    def test_complementary_duplicates_are_merged(self):
        a = example() | {'processo': '', 'unidade_orgao_municipio_nome': 'Campinas'}
        b = example() | {'processo': '123/2026', 'unidade_orgao_municipio_nome': ''}
        data, warnings = select_candidate([a, b])
        self.assertEqual(data['process_number'], '123/2026')
        self.assertEqual(data['city'], 'Campinas')
        self.assertTrue(any('complementadas' in w for w in warnings))
        self.assertEqual(select_candidate([a,b]), select_candidate([b,a]))

    def test_actual_conflicts_have_field_evidence(self):
        with self.assertRaises(DuplicateConflict) as result:
            select_candidate([example(), example() | {'valor_total_estimado': '100'}])
        self.assertEqual(set(result.exception.fields['estimated_value']), {0,100})

    def test_invalid_optional_fields_preserve_pncp_data(self):
        for changes in ({'link_sistema_origem': 'texto'},
                        {'link_sistema_origem': 'https://[invalid'},
                        {'link_sistema_origem': 'https://example.org:xyz'},
                        {'unidade_orgao_codigo_unidade': '1000000'},
                        {'unidade_orgao_codigo_unidade': 'texto'}):
            with self.subTest(changes=changes):
                data, warnings = normalize(example() | changes)
                self.assertEqual(data['description'], 'Compra de cadeiras')
                self.assertNotIn('id_comprasgov', data)
                self.assertTrue(warnings)
                self.assertTrue(data['detail_url'].startswith('https://pncp.gov.br/'))

    def test_merging_dates_must_not_create_invalid_period(self):
        a=example() | {'data_abertura_proposta_pncp': '2026-04-01'}
        b=example() | {'data_encerramento_proposta_pncp': '2026-03-01'}
        with self.assertRaises(ValueError):
            select_candidate([a,b])

    def test_do_not_fill_from_older_revision(self):
        a=example() | {'processo': '123/2026'}
        b=example() | {'processo': '', 'data_atualizacao_pncp': '2026-03-01'}
        data, _ = select_candidate([a,b])
        self.assertIsNone(data['process_number'])

    def test_whitespace_only_differences_are_equivalent(self):
        a=example() | {'objeto_compra': 'Compra  de cadeiras'}
        data, _ = select_candidate([example(),a])
        self.assertEqual(' '.join(data['description'].split()), 'Compra de cadeiras')

    def test_optional_id_conflict_does_not_discard_object(self):
        a=example() | {'id_compra': '20010905900032025', 'link_sistema_origem': ''}
        b=example() | {'link_sistema_origem': ''}
        data, warnings = select_candidate([a,b])
        self.assertNotIn('id_comprasgov',data)
        self.assertEqual(data['description'],'Compra de cadeiras')
        self.assertTrue(any('id_compra divergente' in w for w in warnings))

    def test_modality_and_cnpj(self):
        data, _ = normalize(example())
        self.assertEqual(data['modality_code'], 6)
        self.assertEqual(data['buyer_cnpj'], '00394494010441')
        self.assertEqual(data['estimated_value'], 0)

    def test_invalid_identity_and_dates(self):
        for update in ({'orgao_entidade_cnpj': 123},
                       {'data_abertura_proposta_pncp': 'texto deslocado'},
                       {'data_abertura_proposta_pncp': '2026-03-02', 'data_encerramento_proposta_pncp': '2026-03-01'}):
            with self.assertRaises(ValueError):
                normalize(example() | update)

    def test_mismatched_purchase_id_is_omitted(self):
        data, warnings = normalize(example() | {'id_compra': '20010905900032025'})
        self.assertNotIn('id_comprasgov', data)
        self.assertTrue(warnings)

    def test_excluded_and_old_flags_with_spaces(self):
        for changes in ({'contratacao_excluida': ' true '}, {'ind_atual': ' 0 '}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                normalize(example() | changes)

    def test_overflow_and_negative_amount(self):
        for value in ('1e999', '-0.01', 'Infinity'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(example() | {'valor_total_estimado': value})

    def test_purchase_id_must_match_uasg_and_number(self):
        for changes in ({'unidade_orgao_codigo_unidade': 999999}, {'numero_compra': 90004}):
            data, warnings = normalize(example() | changes)
            self.assertNotIn('id_comprasgov', data)
            self.assertTrue(warnings)

    def test_purchase_id_preserves_leading_zeros(self):
        data, _ = normalize(example() | {'unidade_orgao_codigo_unidade': 123,
                                        'id_compra': '00012305900032026',
                                        'link_sistema_origem': ''})
        self.assertEqual(data['uasg'], '000123')
        self.assertEqual(data['id_comprasgov'], '00012305900032026')

    def test_revision_order_uses_instants_not_text(self):
        a = example() | {'data_atualizacao_pncp': '2026-02-27T09:00:00+00:00', 'objeto_compra': 'Antigo'}
        b = example() | {'data_atualizacao_pncp': '2026-02-27T08:00:00-03:00', 'objeto_compra': 'Recente'}
        data, _ = select_candidate([a, b])
        self.assertEqual(data['description'], 'Recente')

    def test_ambiguous_revisions_are_quarantined(self):
        for value in ('', '2026-02-27T10:00:00-03:00'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                select_candidate([example(), example() | {'data_atualizacao_pncp': value}])

    def test_equal_instants_with_different_contents_are_conflict(self):
        a = example() | {'data_atualizacao_pncp': '2026-02-27T11:00:00Z'}
        b = example() | {'data_atualizacao_pncp': '2026-02-27T08:00:00-03:00', 'objeto_compra': 'Outro'}
        with self.assertRaises(ValueError):
            select_candidate([a, b])

    def test_latest_deleted_record_does_not_resurrect_old_data(self):
        b = example() | {'data_atualizacao_pncp': '2026-02-28 07:00:00', 'contratacao_excluida': '1'}
        with self.assertRaises(ValueError):
            select_candidate([example(), b])

    def test_gap_preserves_zero_and_literal_null(self):
        changes, differences, _ = plan_gaps(
            {'estimated_value': 0, 'description': 'null', 'city': '  '},
            {'estimated_value': 99, 'description': 'Novo texto', 'city': 'Campinas'})
        self.assertEqual(changes, {'city': 'Campinas'})
        self.assertEqual(set(differences), {'estimated_value', 'description'})

    def test_merged_period_is_validated(self):
        with self.assertRaises(ValueError):
            plan_gaps({'proposal_start_at': None, 'proposal_end_at': '2026-02-01'},
                      {'proposal_start_at': '2026-03-01', 'proposal_end_at': '2026-04-01'})

    def test_target_identity_mismatch_blocks_update(self):
        data, _ = normalize(example())
        for field, value in [('pncp_control_number', 'outro'), ('source_cnpj', '123'), ('year', 2025)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                plan_gaps(data | {field: value}, data)

    def test_numeric_and_date_equivalence(self):
        changes, differences, _ = plan_gaps(
            {'estimated_value': 0, 'published_at': '2026-02-27T08:00:00-03:00'},
            {'estimated_value': 0.0, 'published_at': '2026-02-27T11:00:00Z'})
        self.assertEqual(changes, {})
        self.assertEqual(differences, {})

    def test_simulation_preserves_database_and_quarantines_conflicting_ties(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.sqlite'
            row = example()
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE oportunidades_temporarias (' + ','.join('"'+k+'" TEXT' for k in row) + ')')
                insert = 'INSERT INTO oportunidades_temporarias VALUES (' + ','.join('?' for _ in row) + ')'
                db.execute(insert, tuple(row.values()))
                db.execute(insert, tuple(row.values()))
                conflict = row | {'numero_controle_pncp': '00394494010441-1-000090/2026', 'sequencial_compra_pncp': 90,
                                  'numero_compra': 90004, 'id_compra': '20010905900042026',
                                  'link_sistema_origem': 'https://example.org/?compra=20010905900042026'}
                db.execute(insert, tuple(conflict.values()))
                db.execute(insert, tuple((conflict | {'objeto_compra': 'Outro objeto'}).values()))
                db.execute('CREATE TABLE opportunities (id TEXT PRIMARY KEY, external_key TEXT, pncp_control_number TEXT, description TEXT, estimated_value REAL, id_comprasgov TEXT)')
                db.execute('INSERT INTO opportunities VALUES (?,?,?,?,?,?)', ('a',row['numero_controle_pncp'],row['numero_controle_pncp'],'Texto preservado',0,None))
            db.close()
            before = hashlib.sha256(path.read_bytes()).digest()
            summary, _ = simulate(path, 'oportunidades_temporarias', Path(directory)/'reports')
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).digest())
            self.assertEqual(summary['contagens']['existentes'], 1)
            self.assertEqual(summary['contagens']['grupos_para_revisao'], 1)
            self.assertEqual(summary['lacunas_por_coluna'], {'id_comprasgov': 1})
            self.assertEqual(summary['divergencias_preservadas_por_coluna']['description'], 1)

    def test_cross_opportunity_purchase_id_is_not_proposed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'db.sqlite'
            row = example()
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE staging (' + ','.join('"'+k+'" TEXT' for k in row) + ')')
                insert = 'INSERT INTO staging VALUES (' + ','.join('?' for _ in row) + ')'
                db.execute(insert, tuple(row.values()))
                db.execute(insert, tuple((row | {'numero_controle_pncp': '00394494010441-1-000090/2026',
                                                'sequencial_compra_pncp': 90}).values()))
                db.execute('CREATE TABLE opportunities (id TEXT PRIMARY KEY, external_key TEXT, pncp_control_number TEXT, id_comprasgov TEXT)')
            db.close()
            summary, _ = simulate(path, 'staging', Path(directory)/'reports')
            decisions = [json.loads(line) for line in Path(summary['detalhes']).read_text(encoding='utf-8').splitlines()]
            self.assertEqual(summary['contagens']['novas_propostas'], 2)
            self.assertTrue(all('id_comprasgov' not in r['dados'] for r in decisions))
            self.assertTrue(all(r['avisos'] for r in decisions))

    def test_missing_source_and_destination_are_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'missing.sqlite'
            with self.assertRaises(FileNotFoundError):
                simulate(path, 'staging', Path(directory)/'reports')
            self.assertFalse(path.exists())
            with sqlite3.connect(path) as db:
                db.execute('CREATE TABLE unrelated (a TEXT)')
            db.close()
            with self.assertRaises(ValueError):
                simulate(path, 'staging', Path(directory)/'reports')


if __name__ == '__main__':
    unittest.main()
