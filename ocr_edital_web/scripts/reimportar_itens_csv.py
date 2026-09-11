"""Reimporta CSV de itens em tabela nova e valida todos os campos antes do commit."""
import argparse
import csv
import hashlib
import json
from contextlib import closing
from datetime import datetime
from pathlib import Path
import re
import shutil
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
TABLE = 'comprasGOV_anual_VW_FT_PNCP_COMPRA_ITEM_latest_validado'


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def digest_row(digest, row):
    digest.update(json.dumps(list(row), ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    digest.update(b'\n')


def import_csv(source, database, table=TABLE, report_dir=None):
    source = Path(source).resolve(strict=True)
    database = Path(database).resolve(strict=True)
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*_validado', table):
        raise ValueError('destino deve ser uma nova tabela com sufixo _validado')
    if shutil.disk_usage(database.parent).free < source.stat().st_size * 3 + 512 * 1024**2:
        raise ValueError('espaco insuficiente para importacao e indices')
    report_dir = Path(report_dir or database.parent / 'relatorios_importacao')
    report_dir.mkdir(parents=True, exist_ok=True)
    csv.field_size_limit(20 * 1024 * 1024)
    started = time.perf_counter()
    signature = (source.stat().st_size, source.stat().st_mtime_ns)
    expected, actual = hashlib.sha256(), hashlib.sha256()
    count = 0
    quoted = quote(table)
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=60)) as db:
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute('SELECT 1 FROM sqlite_master WHERE name=?', (table,)).fetchone():
                raise ValueError('tabela de destino ja existe; nenhuma substituicao realizada')
            with source.open(encoding='utf-8-sig', newline='') as stream:
                reader = csv.reader(stream, delimiter=',', quotechar='"', doublequote=True, strict=True)
                header = next(reader)
                required = {'srk_pncp_item_compra', 'descricao_detalhada', 'descricao_resumida',
                            'id_compra_item', 'numero_controle_PNCP_compra', 'numero_item_pncp'}
                if len(header) != len(set(h.lower() for h in header)) or not required <= set(header):
                    raise ValueError('cabecalho invalido')
                db.execute(f'CREATE TABLE {quoted} (' + ','.join(quote(h) + ' TEXT' for h in header) + ')')
                insert = f'INSERT INTO {quoted} VALUES (' + ','.join('?' for _ in header) + ')'
                id_index = header.index('srk_pncp_item_compra')
                batch = []
                for row in reader:
                    if len(row) != len(header) or not row[id_index].isdigit():
                        raise ValueError(f'registro CSV invalido: {count + 1}, linha fisica {reader.line_num}')
                    digest_row(expected, row)
                    batch.append(row)
                    count += 1
                    if len(batch) == 1000:
                        db.executemany(insert, batch)
                        batch.clear()
                    if count % 250000 == 0:
                        print(f'Importados {count} registros...', flush=True)
                if batch:
                    db.executemany(insert, batch)
            if signature != (source.stat().st_size, source.stat().st_mtime_ns):
                raise ValueError('arquivo de origem mudou durante a importacao')
            print('Comparando todos os campos gravados com o CSV...', flush=True)
            verified = 0
            for row in db.execute(f'SELECT * FROM {quoted} ORDER BY rowid'):
                digest_row(actual, row)
                verified += 1
            if count != verified or expected.digest() != actual.digest():
                raise ValueError('conteudo gravado diverge do CSV; transacao cancelada')
            print('Conteudo identico. Criando indices de identificacao...', flush=True)
            db.execute(f'CREATE INDEX {quote(table + "_srk")} ON {quoted}(srk_pncp_item_compra)')
            db.execute(f'CREATE INDEX {quote(table + "_pncp_item")} ON {quoted}(numero_controle_PNCP_compra, numero_item_pncp)')
            if db.execute(f'PRAGMA quick_check({quoted})').fetchall() != [('ok',)]:
                raise ValueError('falha na verificacao estrutural da nova tabela')
            db.commit()
        except BaseException:
            db.rollback()
            raise
    result = dict(status='aplicado_e_validado', origem=str(source), banco=str(database),
                  tabela=table, registros=count, colunas=len(header), sha256_conteudo=actual.hexdigest(),
                  todos_campos_identicos=True, tipos='TEXT', tabela_anterior_preservada=True,
                  duracao_segundos=round(time.perf_counter()-started, 2))
    output = report_dir / ('reimportacao_itens_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    print(f'Relatorio: {output}', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, required=True)
    parser.add_argument('--banco', type=Path, default=ROOT / 'data/pncp.sqlite3')
    args = parser.parse_args()
    import_csv(args.csv, args.banco)
