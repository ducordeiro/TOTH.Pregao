"""Planeja e integra itens CSV validados sem substituir itens existentes."""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import groupby
import json
import math
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from etl.models import OpportunityItem
from etl.repository import ETLRepository

TABLE = 'comprasGOV_anual_VW_FT_PNCP_COMPRA_ITEM_latest_validado'
CONTROL = re.compile(r'^(\d{14})-1-(\d{6})/(\d{4})$')
COLUMNS = ('numero_controle_PNCP_compra', 'numero_item_pncp', 'numero_grupo',
           'descricao_resumida', 'id_compra_item', 'quantidade', 'unidade_medida',
           'valor_unitario_estimado', 'valor_total', 'data_atualizacao_pncp',
           'situacao_compra_item_nome', 'orgao_entidade_cnpj', 'ano_compra',
           'sequencial_compra', 'ID_contratacao_PNCP')


def clean(value):
    return None if value is None or str(value).strip().lower() in ('', 'null', 'none', 'nan') else str(value).strip()


def integer(value):
    number = Decimal(clean(value) or '0')
    if not number.is_finite() or number != number.to_integral_value() or number < 0:
        raise ValueError('inteiro invalido')
    return int(number)


def numeric(value):
    if clean(value) is None:
        return None
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('quantidade ou valor invalido')
    return result


def select_item(rows, key):
    match = CONTROL.fullmatch(key)
    if not match:
        raise ValueError('chave PNCP invalida')
    cnpj, sequence, year = match.groups()
    versions = []
    for row in rows:
        raw = clean(row['data_atualizacao_pncp'])
        versions.append(datetime.fromisoformat(raw.replace('Z', '+00:00')) if raw else None)
    if None in versions and any(v is not None for v in versions):
        raise ValueError('revisoes sem data comparavel')
    if len({v.tzinfo is None for v in versions if v is not None}) > 1:
        raise ValueError('revisoes com fusos ambiguos')
    newest = max(versions) if versions[0] else None
    candidates = []
    for row, version in zip(rows, versions):
        if version != newest:
            continue
        for field, expected in (('orgao_entidade_cnpj', cnpj), ('ano_compra', year), ('sequencial_compra', sequence)):
            if clean(row[field]) and integer(row[field]) != int(expected):
                raise ValueError('identidade divergente: ' + field)
        if clean(row['ID_contratacao_PNCP']) and clean(row['ID_contratacao_PNCP']) != key:
            raise ValueError('identificacoes PNCP divergentes')
        description = clean(row['descricao_resumida'])
        if not description:
            raise ValueError('descricao do item ausente')
        number = integer(row['numero_item_pncp'])
        if number == 0:
            raise ValueError('numero de item ausente')
        lot = integer(row['numero_grupo'])
        candidates.append(dict(source_item_id=clean(row['id_compra_item']),
                               item_number=str(number), lot_number=str(lot) if lot else '',
                               title=description, description=description,
                               quantity=numeric(row['quantidade']), unit=clean(row['unidade_medida']),
                               estimated_unit_value=numeric(row['valor_unitario_estimado']),
                               estimated_total_value=numeric(row['valor_total']),
                               status=clean(row['situacao_compra_item_nome'])))
    merged = {}
    for field in candidates[0]:
        values = {r[field] for r in candidates if r[field] is not None}
        if len(values) > 1:
            if field in ('status', 'source_item_id'):
                merged[field] = None
                continue
            raise ValueError('duplicatas conflitantes: ' + field)
        merged[field] = next(iter(values)) if values else None
    return merged


def plan(database, output):
    started = time.perf_counter()
    output.mkdir(parents=True, exist_ok=True)
    path = output / ('plano_integracao_itens_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.jsonl')
    counts, reasons = Counter(), Counter()
    touched = set()
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True, timeout=60)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        lookup = {}
        for row in db.execute('SELECT id,external_key,pncp_control_number FROM opportunities'):
            for key in (row['external_key'], row['pncp_control_number']):
                if key:
                    lookup.setdefault(key, set()).add(row['id'])
        query = 'SELECT ' + ','.join(COLUMNS) + ' FROM ' + TABLE + ' ORDER BY numero_controle_PNCP_compra,numero_item_pncp'
        with path.open('x', encoding='utf-8') as stream:
            for key, opportunity_rows in groupby(db.execute(query), lambda r: r['numero_controle_PNCP_compra']):
                ids = lookup.get(key, set())
                existing = set()
                target = None
                if len(ids) == 1:
                    target = db.execute('SELECT * FROM opportunities WHERE id=?', (next(iter(ids)),)).fetchone()
                    existing = {str(r[0]).strip().lstrip('0') or '0' for r in db.execute('SELECT item_number FROM opportunity_items WHERE opportunity_id=?', (target['id'],))}
                for number, group in groupby(opportunity_rows, lambda r: r['numero_item_pncp']):
                    rows = [dict(r) for r in group]
                    counts['linhas_origem'] += len(rows)
                    counts['grupos_itens'] += 1
                    action, reason, item = 'revisar', None, None
                    try:
                        if not ids:
                            action = 'sem_oportunidade'
                        elif len(ids) > 1:
                            raise ValueError('vinculo de oportunidade ambiguo')
                        elif str(integer(number)) in existing:
                            action = 'preservar_existente'
                        else:
                            item = select_item(rows, key)
                            match = CONTROL.fullmatch(key)
                            for field, expected in (('source_cnpj', match[1]), ('buyer_cnpj', match[1]), ('sequence', match[2]), ('year', match[3])):
                                if clean(target[field]) and integer(re.sub(r'[^0-9]', '', str(target[field]))) != int(expected):
                                    raise ValueError('identidade da oportunidade divergente')
                            action = 'inserir'
                            touched.add(target['id'])
                    except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
                        reason = str(exc)
                        reasons[reason] += 1
                    counts[action] += 1
                    if action in ('inserir', 'revisar', 'sem_oportunidade'):
                        stream.write(json.dumps(dict(acao=action, chave=key, numero=number,
                            opportunity_id=target['id'] if target else None, item=item, motivo=reason), ensure_ascii=False) + '\n')
                    if counts['grupos_itens'] % 100000 == 0:
                        print(f"Analisados {counts['grupos_itens']} grupos de itens...", flush=True)
        db.rollback()
    result = dict(contagens=dict(counts), motivos=dict(reasons), oportunidades_com_novos_itens=len(touched), plano=str(path), segundos=round(time.perf_counter()-started, 2))
    path.with_suffix('.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    return path


def apply_plan(database, path):
    started = time.perf_counter()
    repository = ETLRepository(database)
    counts = Counter()
    touched = set()
    now = datetime.now(timezone.utc).isoformat()
    with repository.connect() as db, db:
        db.execute('BEGIN IMMEDIATE')
        with path.open(encoding='utf-8') as stream:
            for line in stream:
                row = json.loads(line)
                if row['acao'] != 'inserir':
                    continue
                opp_id = row['opportunity_id']
                target = db.execute('SELECT external_key,pncp_control_number FROM opportunities WHERE id=?', (opp_id,)).fetchone()
                if target is None or row['chave'] not in tuple(target):
                    raise ValueError('vinculo mudou desde o plano')
                item = OpportunityItem(**row['item'])
                exists = db.execute("SELECT 1 FROM opportunity_items WHERE opportunity_id=? AND ltrim(trim(item_number),'0')=?", (opp_id, item.item_number.lstrip('0'))).fetchone()
                if exists:
                    counts['preservados_na_revalidacao'] += 1
                    continue
                repository._insert_items(db, opp_id, [item], now)
                touched.add(opp_id)
                counts['itens_inseridos'] += 1
                if counts['itens_inseridos'] % 50000 == 0:
                    print(f"Inseridos {counts['itens_inseridos']} itens...", flush=True)
        print(f'Atualizando busca e classificacao de {len(touched)} oportunidades...', flush=True)
        for index, opp_id in enumerate(sorted(touched), 1):
            repository._refresh_object_classification(db, opp_id, now)
            if not db.execute('SELECT 1 FROM opportunity_search WHERE rowid=(SELECT rowid FROM opportunities WHERE id=?)', (opp_id,)).fetchone():
                raise ValueError('oportunidade ausente no indice de busca')
            if index % 5000 == 0:
                print(f'Indexadas {index} oportunidades...', flush=True)
        if db.execute("PRAGMA quick_check('opportunity_items')").fetchall()[0][0] != 'ok':
            raise ValueError('integridade dos itens falhou')
    result = dict(status='aplicado', contagens=dict(counts), oportunidades_atualizadas=len(touched), plano=str(path), segundos=round(time.perf_counter()-started, 2))
    report = path.with_name(path.stem + '_aplicado.json')
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--banco', type=Path, default=ROOT / 'data/pncp.sqlite3')
    parser.add_argument('--aplicar-plano', type=Path)
    args = parser.parse_args()
    if args.aplicar_plano:
        apply_plan(args.banco, args.aplicar_plano)
    else:
        plan(args.banco, ROOT / 'data/relatorios_importacao')
