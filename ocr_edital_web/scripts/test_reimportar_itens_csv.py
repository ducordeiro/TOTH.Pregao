import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from reimportar_itens_csv import import_csv, TABLE


class CsvImportTest(unittest.TestCase):
    def test_exact_text_and_rollback(self):
        header = ['srk_pncp_item_compra', 'descricao_detalhada', 'descricao_resumida',
                  'id_compra_item', 'numero_controle_PNCP_compra', 'numero_item_pncp']
        row = ['1', 'Texto "com aspas", virgula\r\ne outra linha', '',
               '001353150590007202500001', '00123456000199-1-000001/2026', '01']
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source, dbpath = path / 'source.csv', path / 'test.sqlite'
            with closing(sqlite3.connect(dbpath)) as db:
                db.execute('CREATE TABLE original (value TEXT)')
                db.commit()
            with source.open('w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f).writerows([header, row])
            result = import_csv(source, dbpath)
            self.assertEqual(result['registros'], 1)
            with closing(sqlite3.connect(dbpath)) as db:
                self.assertEqual(db.execute('SELECT * FROM ' + TABLE).fetchone(), tuple(row))
                self.assertEqual(len(db.execute('PRAGMA index_list(' + TABLE + ')').fetchall()), 2)
            with self.assertRaises(ValueError):
                import_csv(source, dbpath)
            with source.open('w', encoding='utf-8', newline='') as f:
                csv.writer(f).writerows([header, row, ['invalid']])
            with self.assertRaises(ValueError):
                import_csv(source, dbpath, 'bad_validado')
            with closing(sqlite3.connect(dbpath)) as db:
                self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='bad_validado'").fetchone())
                self.assertEqual(db.execute('SELECT count(*) FROM ' + TABLE).fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()
