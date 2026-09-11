"""Importa uma tabela Compras.gov com simulacao ou aplicacao transacional.

Uso: python scripts/importar_comprasgov.py --simular
Os arquivos de relatorio sao gravados em data/relatorios_importacao.
Use --aplicar para criar backup, revalidar e gravar as alteracoes aprovadas.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from itertools import groupby
import json
import math
import hashlib
import shutil
import uuid
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTROL = re.compile(r"^(\d{14})-1-(\d{6})/(\d{4})$")
UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())
TEXT_FIELDS = {
    'process_number': 'processo', 'description': 'objeto_compra',
    'buyer_name': 'orgao_entidade_razao_social', 'uf': 'unidade_orgao_uf_sigla',
    'city': 'unidade_orgao_municipio_nome', 'modality': 'modalidade_nome',
    'status': 'situacao_compra_nome_pncp',
}
DATE_FIELDS = {'published_at': 'data_publicacao_pncp',
               'proposal_start_at': 'data_abertura_proposta_pncp',
               'proposal_end_at': 'data_encerramento_proposta_pncp'}


class DuplicateConflict(ValueError):
    def __init__(self, fields):
        super().__init__('duplicidade conflitante na mesma data de atualizacao')
        self.fields = fields


def clean(value):
    if value is None:
        return None
    value = str(value).strip()
    return None if value.lower() in {'', 'null', 'none', 'nan'} else value


def integer(value):
    raw = clean(value)
    if raw is None:
        return None
    number = Decimal(raw)
    if not number.is_finite() or number != number.to_integral_value() or number < 0:
        raise ValueError('inteiro invalido')
    return int(number)


def date_value(value):
    raw = clean(value)
    if raw is None:
        return None
    return datetime.fromisoformat(raw.replace('Z', '+00:00')).isoformat()


def date_order(value):
    dt = datetime.fromisoformat(date_value(value))
    return dt.astimezone(timezone.utc) if dt.tzinfo is not None else dt


def validate_period(data):
    start, end = data.get('proposal_start_at'), data.get('proposal_end_at')
    if clean(start) and clean(end):
        a, b = date_order(start), date_order(end)
        if (a.tzinfo is None) != (b.tzinfo is None):
            raise ValueError('periodo com fuso horario ambiguo')
        if b < a:
            raise ValueError('encerramento anterior ao inicio')


def blank(value):
    # No destino, sentinelas textuais sao dados existentes, nao lacunas.
    return value is None or (isinstance(value, str) and not value.strip())


def normalize(row):
    warnings = []
    key = (clean(row['numero_controle_pncp']) or '').upper()
    match = CONTROL.fullmatch(key)
    if not match:
        raise ValueError('numero_controle_pncp ausente ou invalido')
    cnpj, seq, year = match.groups()
    for name, expected in [('orgao_entidade_cnpj', int(cnpj)),
                           ('sequencial_compra_pncp', int(seq)), ('ano_compra_pncp', int(year))]:
        if clean(row.get(name)) is not None and integer(row[name]) != expected:
            raise ValueError(f'{name} diverge do numero PNCP')
    for name in ('contratacao_excluida', 'ind_atual'):
        raw = (clean(row.get(name)) or '').lower()
        if raw not in {'', '0', '1', 'false', 'true', '0.0', '1.0'}:
            raise ValueError(f'{name} invalido')
    if (clean(row.get('contratacao_excluida')) or '').lower() in {'1', 'true', '1.0'}:
        raise ValueError('contratacao marcada como excluida na fonte')
    if (clean(row.get('ind_atual')) or '').lower() in {'0', 'false', '0.0'}:
        raise ValueError('versao marcada como nao atual')
    data = {target: clean(row.get(source)) for target, source in TEXT_FIELDS.items()}
    for value in data.values():
        if value and '\ufffd' in value:
            raise ValueError('texto contem caractere de substituicao de codificacao')
    data['uf'] = data['uf'].upper() if data['uf'] else None
    if data['uf'] and data['uf'] not in UFS:
        raise ValueError('UF invalida')
    data.update({target: date_value(row.get(source)) for target, source in DATE_FIELDS.items()})
    validate_period(data)
    value = clean(row.get('valor_total_estimado'))
    if value is not None:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0:
            raise ValueError('valor estimado invalido')
        data['estimated_value'] = float(amount)
        if not math.isfinite(data['estimated_value']):
            raise ValueError('valor estimado excede a capacidade do banco')
    modality = integer(row.get('modalidade_id_pncp'))
    if modality is not None and not 1 <= modality <= 19:
        raise ValueError('modalidade PNCP invalida')
    data['modality_code'] = modality
    invalid_uasg = False
    try:
        uasg = integer(row.get('unidade_orgao_codigo_unidade'))
        if uasg is not None and not 0 < uasg <= 999999:
            raise ValueError('UASG invalida')
    except (ValueError, InvalidOperation, OverflowError):
        uasg = None
        invalid_uasg = True
        warnings.append('UASG invalida; UASG e id_compra omitidos')
    data['uasg'] = str(uasg).zfill(6) if uasg is not None else None
    number = integer(row.get('numero_compra'))
    data.update(external_key=key, pncp_control_number=key, source='comprasgov',
                source_cnpj=cnpj, buyer_cnpj=cnpj, year=int(year), sequence=int(seq),
                title=f'Edital {number}' if number is not None else f'Oportunidade {key}', currency='BRL')
    link = clean(row.get('link_sistema_origem'))
    invalid_link = False
    try:
        parsed = urlparse(link or '')
        if link and (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                     or parsed.username or parsed.password or any(ch.isspace() for ch in link)):
            raise ValueError('link invalido')
        if link:
            parsed.port
    except ValueError:
        link = None
        invalid_link = True
        warnings.append('link de origem invalido; link e id_compra omitidos; pagina PNCP usada')
    detail = f'https://pncp.gov.br/app/editais/{cnpj}/{year}/{int(seq)}'
    data.update(detail_url=detail, origin_url=link, source_url=link or detail)
    purchase_id = clean(row.get('id_compra'))
    if purchase_id and not (invalid_link or invalid_uasg):
        url_ids = parse_qs(urlparse(link or '').query).get('compra', [])
        if (not re.fullmatch(r'[0-9]{17}', purchase_id)
                or (url_ids and any(v != purchase_id for v in url_ids))
                or (data['uasg'] and purchase_id[:6] != data['uasg'])
                or (number is not None and purchase_id[8:13] != str(number).zfill(5))):
            warnings.append('id_compra invalido ou divergente do link; campo omitido')
        else:
            data['id_comprasgov'] = purchase_id
    return data, warnings


def revision(row):
    raw = clean(row.get('data_atualizacao_pncp'))
    if raw is None:
        return None
    return date_order(raw)


def select_candidate(rows):
    versions = [revision(r) for r in rows]
    if None in versions and any(v is not None for v in versions):
        raise ValueError('duplicidade com data de atualizacao ausente')
    if len({v.tzinfo is None for v in versions if v is not None}) > 1:
        raise ValueError('duplicidade com fuso horario ambiguo')
    newest = max(versions) if versions[0] is not None else None
    candidates = [normalize(r) for r, v in zip(rows, versions) if v == newest]
    warnings = sorted({w for _, notes in candidates for w in notes})
    merged, conflicts = {}, {}
    complemented = []
    for field in sorted({k for data, _ in candidates for k in data}):
        values = [data[field] for data, _ in candidates if not blank(data.get(field))]
        equivalents = {}
        for value in values:
            if field in DATE_FIELDS:
                token = str(date_order(value))
            elif isinstance(value, str) and field in TEXT_FIELDS:
                token = ' '.join(value.split())
                if field == 'description':
                    token = token.replace("'", '"')
            else:
                token = json.dumps(value, sort_keys=True, allow_nan=False)
            equivalents.setdefault(token, []).append(value)
        if len(equivalents) > 1:
            conflicts[field] = sorted(set(values), key=str)
        elif values:
            if field == 'description':
                # Escolhe uma versao real da origem, preservando apostrofos nela.
                merged[field] = min(values, key=lambda v: (-v.count('"'), v))
                if len({' '.join(v.split()) for v in values}) > 1:
                    warnings.append('descricao equivalente entre aspas; versao com aspas duplas priorizada')
            else:
                merged[field] = sorted(values, key=str)[0]
            if len(values) < len(candidates):
                complemented.append(field)
        else:
            merged[field] = None
    # A identidade externa opcional nao deve bloquear dados PNCP consistentes.
    if 'id_comprasgov' in conflicts:
        conflicts.pop('id_comprasgov')
        merged.pop('id_comprasgov', None)
        warnings.append('id_compra divergente entre duplicatas; campo omitido')
    if any('id_compra' in w for w in warnings):
        merged.pop('id_comprasgov', None)
    if conflicts:
        raise DuplicateConflict(conflicts)
    validate_period(merged)
    if complemented:
        warnings.append('duplicatas complementadas sem conflito: ' + ', '.join(complemented))
    return merged, warnings


def plan_gaps(target, data):
    # A chave so pode ligar registros com a mesma identidade PNCP.
    for field in ('pncp_control_number', 'source_cnpj', 'buyer_cnpj', 'year', 'sequence'):
        old, new = target.get(field), data.get(field)
        if not blank(old) and new is not None:
            if field in {'year', 'sequence'}:
                same = integer(old) == new
            elif field.endswith('cnpj'):
                same = re.sub(r'[^0-9]', '', str(old)).zfill(14) == new
            else:
                same = str(old).strip().upper() == new
            if not same:
                raise ValueError(f'identidade do destino divergente: {field}')
    changes, differences, warnings = {}, {}, []
    for field, value in data.items():
        if field in {'source', 'external_key'} or value is None:
            continue
        if field not in target:
            warnings.append(f'coluna de destino ausente: {field}')
            continue
        old = target[field]
        if blank(old):
            changes[field] = value
        else:
            equivalent = str(old).strip() == str(value).strip()
            if field in DATE_FIELDS:
                try:
                    equivalent = date_order(old) == date_order(value)
                except (TypeError, ValueError):
                    pass
            elif field == 'estimated_value':
                try:
                    equivalent = Decimal(str(old)) == Decimal(str(value))
                except InvalidOperation:
                    pass
            if not equivalent:
                differences[field] = {'banco': old, 'origem': value}
    if {'proposal_start_at', 'proposal_end_at'} & changes.keys():
        validate_period(target | changes)
    return changes, differences, warnings


def simulate(database, table, output):
    started = time.perf_counter()
    database = Path(database).resolve(strict=True)
    output = Path(output).resolve()
    if output == database or database in output.parents:
        raise ValueError('diretorio de relatorio invalido')
    output.mkdir(parents=True, exist_ok=True)
    # mode=ro + query_only protegem a base, inclusive contra gravacoes acidentais.
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=60)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        db.create_function('import_key', 1, lambda v: (clean(v) or '').upper(), deterministic=True)
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in tables or table == 'opportunities':
            raise ValueError('tabela de origem inexistente ou igual ao destino')
        quoted = '"' + table.replace('"', '""') + '"'
        columns = {r[1] for r in db.execute(f'PRAGMA table_info({quoted})')}
        required = {'numero_controle_pncp', 'id_compra', 'data_atualizacao_pncp',
                    'modalidade_id_pncp', 'orgao_entidade_cnpj', 'ano_compra_pncp',
                    'sequencial_compra_pncp', 'ind_atual', 'contratacao_excluida',
                    'valor_total_estimado', 'unidade_orgao_codigo_unidade', 'numero_compra',
                    'link_sistema_origem', *TEXT_FIELDS.values(), *DATE_FIELDS.values()}
        if required - columns:
            raise ValueError('colunas ausentes: ' + ', '.join(sorted(required - columns)))
        lookup = {}
        target_columns = {r[1] for r in db.execute('PRAGMA table_info(opportunities)')}
        missing_target = {'id', 'external_key', 'pncp_control_number'} - target_columns
        if missing_target:
            raise ValueError('identificacao ausente no destino: ' + ', '.join(sorted(missing_target)))
        gov_lookup = {}
        gov_column = 'id_comprasgov' if 'id_comprasgov' in target_columns else 'NULL AS id_comprasgov'
        for row in db.execute(f'SELECT id,external_key,pncp_control_number,{gov_column} FROM opportunities'):
            for value in (row['external_key'], row['pncp_control_number']):
                if clean(value):
                    lookup.setdefault(clean(value).upper(), set()).add(row['id'])
            if clean(row['id_comprasgov']):
                gov_lookup.setdefault(clean(row['id_comprasgov']), set()).add(row['id'])
        ambiguous_gov = {r[0] for r in db.execute(
            f'SELECT import_key(id_compra) FROM {quoted} '
            'WHERE import_key(id_compra) != ? GROUP BY import_key(id_compra) '
            'HAVING count(DISTINCT import_key(numero_controle_pncp)) > 1', ('',))}
        count, gaps, conflicts, reasons = Counter(), Counter(), Counter(), Counter()
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        detail_file = output / f'simulacao_{stamp}.jsonl'
        query = f'SELECT * FROM {quoted} ORDER BY import_key(numero_controle_pncp)'
        with detail_file.open('x', encoding='utf-8') as report:
            def emit(obj):
                report.write(json.dumps(obj, ensure_ascii=False, allow_nan=False) + '\n')
            for key, group in groupby(db.execute(query), lambda r: (clean(r['numero_controle_pncp']) or '').upper()):
                rows = [dict(r) for r in group]
                count['linhas_origem'] += len(rows)
                count['grupos'] += 1
                count['linhas_repetidas_por_chave'] += max(0, len(rows)-1)
                try:
                    if not CONTROL.fullmatch(key):
                        raise ValueError('numero_controle_pncp ausente ou invalido')
                    data, warnings = select_candidate(rows)
                    ids = lookup.get(key, set())
                    if len(ids) > 1:
                        raise ValueError('mais de um registro de destino corresponde a chave')
                    gov_id = data.get('id_comprasgov')
                    if gov_id and (gov_id in ambiguous_gov or gov_lookup.get(gov_id, set()) - ids):
                        del data['id_comprasgov']
                        warnings.append('id_compra associado a outras oportunidades; campo omitido')
                    if 'id_comprasgov' in data and 'id_comprasgov' not in target_columns:
                        del data['id_comprasgov']
                        warnings.append('coluna de destino ausente: id_comprasgov')
                    if not ids:
                        if not data['description'] or not data['buyer_name']:
                            raise ValueError('nova oportunidade sem objeto ou orgao')
                        count['novas_propostas'] += 1
                        emit(dict(acao='inserir', chave=key, dados=data, avisos=warnings))
                    else:
                        target = dict(db.execute('SELECT * FROM opportunities WHERE id=?', (next(iter(ids)),)).fetchone())
                        changes, differences, more_warnings = plan_gaps(target, data)
                        warnings.extend(more_warnings)
                        gaps.update(changes.keys())
                        conflicts.update(differences.keys())
                        count['existentes'] += 1
                        count['atualizacoes_propostas' if changes else 'sem_lacunas'] += 1
                        emit(dict(acao='preencher_lacunas' if changes else 'preservar', chave=key,
                                  id=target['id'], alteracoes=changes, divergencias_preservadas=differences, avisos=warnings))
                    count['grupos_com_avisos'] += bool(warnings)
                except (ValueError, TypeError, InvalidOperation, OverflowError) as exc:
                    count['grupos_para_revisao'] += 1
                    count['linhas_para_revisao'] += len(rows)
                    reasons[str(exc)] += 1
                    emit(dict(acao='revisar', chave=key, linhas=len(rows), motivo=str(exc),
                              campos_conflitantes=getattr(exc, 'fields', {}),
                              referencias=[{k: r.get(k) for k in ('cod_compra', 'id_compra', 'data_atualizacao_pncp')} for r in rows]))
                if count['grupos'] % 10000 == 0:
                    print(f"Analisadas {count['grupos']} chaves...", flush=True)
        summary = dict(modo='somente_leitura', banco=str(database), tabela=table,
                       versao_regras=4, duracao_segundos=round(time.perf_counter()-started, 3),
                       gerado_em=datetime.now(timezone.utc).isoformat(), contagens=dict(count),
                       lacunas_por_coluna=dict(gaps), divergencias_preservadas_por_coluna=dict(conflicts),
                       motivos_revisao=dict(reasons), detalhes=str(detail_file),
                       observacao='Plano preliminar. Nao grava, nao baixa itens e nao atualiza indices. Revalidar antes de aplicar.')
        summary_file = output / f'simulacao_{stamp}.json'
        summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
        db.rollback()
        return summary, summary_file


def apply_import(database, table, output):
    """Recalcula o plano sobre um backup consistente, sob bloqueio de escrita."""
    database = Path(database).resolve(strict=True)
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    backup_dir = database.parent / 'backups_importacao'
    backup_dir.mkdir(exist_ok=True)
    if shutil.disk_usage(backup_dir).free < database.stat().st_size * 2 + 512 * 1024**2:
        raise ValueError('espaco insuficiente para backup e transacao')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup = backup_dir / f'pncp_antes_importacao_{stamp}.sqlite3'
    started = time.perf_counter()
    with closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True, timeout=60)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        try:
            print('Criando backup consistente...', flush=True)
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as source:
                with closing(sqlite3.connect(backup)) as dest:
                    source.backup(dest, pages=4096)
                    if dest.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                        raise ValueError('backup falhou na verificacao de integridade')
            summary, plan_file = simulate(backup, table, output)
            before = db.execute('SELECT count(*) FROM opportunities').fetchone()[0]
            columns = {r[1] for r in db.execute('PRAGMA table_info(opportunities)')}
            counts = Counter()
            now = datetime.now(timezone.utc).isoformat()
            with open(summary['detalhes'], encoding='utf-8') as stream:
                for line in stream:
                    row = json.loads(line)
                    action = row['acao']
                    if action == 'inserir':
                        values = row['dados']
                        values.update(id=uuid.uuid4().hex, created_at=now, updated_at=now,
                                      record_hash=hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest())
                        if set(values) - columns:
                            raise ValueError('colunas desconhecidas no plano')
                        names = ','.join('"' + k + '"' for k in values)
                        db.execute(f'INSERT INTO opportunities ({names}) VALUES ({",".join("?" for _ in values)})', list(values.values()))
                    elif action == 'preencher_lacunas':
                        target = db.execute('SELECT * FROM opportunities WHERE id=?', (row['id'],)).fetchone()
                        values = row['alteracoes']
                        if target is None or set(values) - columns or any(not blank(target[k]) for k in values):
                            raise ValueError('destino divergiu do plano; transacao cancelada')
                        values = values | {'updated_at': now}
                        assignments = ','.join('"' + k + '"=?' for k in values)
                        db.execute(f'UPDATE opportunities SET {assignments} WHERE id=?', [*values.values(), row['id']])
                    counts[action] += 1
            after = db.execute('SELECT count(*) FROM opportunities').fetchone()[0]
            if after != before + counts['inserir']:
                raise ValueError('contagem final divergente')
            if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('verificacao de integridade falhou')
            db.commit()
        except BaseException:
            db.rollback()
            raise
    result = dict(modo='aplicado', banco=str(database), backup=str(backup), plano=str(plan_file),
                  antes=before, depois=after, contagens=dict(counts),
                  duracao_segundos=round(time.perf_counter()-started, 3))
    filename = output / f'aplicacao_{stamp}.json'
    filename.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result, filename


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--simular', action='store_true')
    mode.add_argument('--aplicar', action='store_true')
    parser.add_argument('--banco', type=Path, default=ROOT / 'data/pncp.sqlite3')
    parser.add_argument('--tabela', default='comprasGOV_organizado')
    parser.add_argument('--relatorios', type=Path, default=ROOT / 'data/relatorios_importacao')
    args = parser.parse_args()
    operation = apply_import if args.aplicar else simulate
    summary, filename = operation(args.banco, args.tabela, args.relatorios)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(f'Relatorio: {filename}')


if __name__ == '__main__':
    main()
