from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from integrar_itens_validados import TABLE, COLUMNS, select_item, plan, apply_plan, ETLRepository

KEY = '00394494010441-1-000089/2026'


def example():
    return dict(zip(COLUMNS, [KEY, '1', '0', 'Cadeira teste exclusiva',
        '0012345678901234567890', '3', 'UNIDADE', '10', '30', '2026-09-09',
        'Homologado', '00394494010441', '2026', '89', KEY]))


class IntegrationTest(unittest.TestCase):
    def test_duplicate_versions_and_conflicts(self):
        row = example()
        self.assertEqual(select_item([row, row], KEY)['source_item_id'], row['id_compra_item'])
        self.assertEqual(select_item([row, row | {'data_atualizacao_pncp': '2026-09-08', 'quantidade': '8'}], KEY)['quantity'], 3)
        with self.assertRaises(ValueError):
            select_item([row, row | {'quantidade': '8'}], KEY)
        with self.assertRaises(ValueError):
            select_item([row | {'orgao_entidade_cnpj': '999'}], KEY)
        with self.assertRaises(ValueError):
            select_item([row | {'descricao_resumida': ''}], KEY)

    def test_apply_preserves_existing_and_indexes_items(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / 'db.sqlite'
            ETLRepository(database).initialize()
            with closing(sqlite3.connect(database)) as db, db:
                db.execute("INSERT INTO opportunities(id,external_key,pncp_control_number,source,title,record_hash,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)", ('opp', KEY, KEY, 'pncp', 'Compra', 'hash', 'now', 'now'))
                db.execute('CREATE TABLE ' + TABLE + '(' + ','.join('"'+k+'" TEXT' for k in COLUMNS) + ')')
                row = example()
                db.execute('INSERT INTO '+TABLE+' VALUES ('+','.join('?' for _ in COLUMNS)+')', [row[k] for k in COLUMNS])
            path = plan(database, root)
            failed_path = root / 'falha.jsonl'
            original = path.read_text(encoding='utf-8')
            invalid = json.loads(original)
            invalid['opportunity_id'] = 'nao-existe'
            failed_path.write_text(original + json.dumps(invalid) + '\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                apply_plan(database, failed_path)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM opportunity_items').fetchone()[0], 0)
            apply_plan(database, path)
            apply_plan(database, path)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM opportunity_items').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT description,source_item_id FROM opportunity_items').fetchone(), (row['descricao_resumida'], row['id_compra_item']))
                self.assertEqual(db.execute("SELECT count(*) FROM opportunity_search WHERE opportunity_search MATCH 'exclusiva'").fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
