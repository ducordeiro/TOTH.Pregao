"""Auditoria de leitura: plano, origem validada, integridade e rotas HTTP locais."""
from collections import Counter
from contextlib import closing
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import random
import sqlite3
import statistics
import sys
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server

PLAN = ROOT / 'data/relatorios_importacao/plano_integracao_itens_20260909_164804.jsonl'
TABLE = 'comprasGOV_anual_VW_FT_PNCP_COMPRA_ITEM_latest_validado'


def run():
    start = time.perf_counter()
    counts, errors = Counter(), []
    sample, opportunities = [], {}
    rng = random.Random(20260910)
    source_fields = {'description': 'descricao_resumida', 'source_item_id': 'id_compra_item',
                     'quantity': 'quantidade', 'unit': 'unidade_medida',
                     'estimated_unit_value': 'valor_unitario_estimado', 'estimated_total_value': 'valor_total'}
    with closing(sqlite3.connect((ROOT / 'data/pncp.sqlite3').as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        for line in PLAN.open(encoding='utf-8'):
            row = json.loads(line)
            if row['acao'] != 'inserir':
                continue
            expected = row['item']
            item = db.execute('SELECT * FROM opportunity_items WHERE opportunity_id=? AND lot_number=? AND item_number=?',
                              (row['opportunity_id'], expected['lot_number'], expected['item_number'])).fetchone()
            counts['itens_do_plano_conferidos'] += 1
            if item is None:
                counts['itens_ausentes'] += 1
            else:
                for field, value in expected.items():
                    if item[field] != value:
                        counts['campos_divergentes_do_plano'] += 1
                        if len(errors) < 10:
                            errors.append(dict(chave=row['chave'], item=expected['item_number'], campo=field))
                counts['descricao_vazia_importados'] += not bool((item['description'] or '').strip())
                counts['id_importado_nao_texto'] += item['source_item_id'] is not None and not isinstance(item['source_item_id'], str)
            opportunities.setdefault(row['opportunity_id'], row)
            if len(sample) < 200:
                sample.append(row)
            else:
                index = rng.randrange(counts['itens_do_plano_conferidos'])
                if index < 200:
                    sample[index] = row
        print('Todos os itens do plano conferidos. Verificando vinculos e indice...', flush=True)
        for oid, row in opportunities.items():
            parent = db.execute('SELECT rowid,external_key,pncp_control_number FROM opportunities WHERE id=?', (oid,)).fetchone()
            if not parent or row['chave'] not in (parent['external_key'], parent['pncp_control_number']):
                counts['vinculos_incorretos'] += 1
                continue
            index = db.execute('SELECT opportunity_id,content FROM opportunity_search WHERE rowid=?', (parent['rowid'],)).fetchone()
            if not index or index['opportunity_id'] != oid:
                counts['oportunidades_sem_indice'] += 1
            elif row['item']['description'] not in index['content']:
                counts['descricoes_ausentes_do_indice_amostra_por_oportunidade'] += 1
        counts['oportunidades_conferidas'] = len(opportunities)
        totals = tuple(db.execute('SELECT count(*),count(DISTINCT opportunity_id) FROM opportunity_items').fetchone())
        counts['itens_orfaos_tabela_inteira'] = db.execute('SELECT count(*) FROM opportunity_items i LEFT JOIN opportunities o ON o.id=i.opportunity_id WHERE o.id IS NULL').fetchone()[0]
        counts['chaves_duplicadas_tabela_inteira'] = db.execute('SELECT count(*) FROM (SELECT 1 FROM opportunity_items GROUP BY opportunity_id,lot_number,item_number HAVING count(*)>1)').fetchone()[0]
        print('Comparando amostra distribuida com a tabela de origem...', flush=True)
        for row in sample:
            originals = db.execute('SELECT * FROM '+TABLE+' WHERE numero_controle_PNCP_compra=? AND numero_item_pncp=?',
                                   (row['chave'], row['numero'])).fetchall()
            if not originals:
                counts['amostra_sem_origem'] += 1
                continue
            for field, source_field in source_fields.items():
                expected = row['item'][field]
                if expected is None:
                    continue
                def equivalent(value):
                    if field in ('quantity', 'estimated_unit_value', 'estimated_total_value'):
                        try:
                            return float(value) == expected
                        except (ValueError, TypeError):
                            return False
                    return str(value).strip() == expected
                if not any(equivalent(original[source_field]) for original in originals):
                    counts['campos_divergentes_da_origem_amostra'] += 1
                    if len(errors) < 10:
                        errors.append(dict(chave=row['chave'], item=row['numero'], campo_origem=source_field))
        counts['itens_comparados_com_origem'] = len(sample)
        db.rollback()
    print('Testando 50 detalhamentos pela rota HTTP do app...', flush=True)
    httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.App)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    timings, http_errors, searches = [], [], []
    base = f'http://127.0.0.1:{httpd.server_port}'
    try:
        for row in sample[:50]:
            before = time.perf_counter()
            try:
                with urlopen(base + '/internal/opportunities/' + row['opportunity_id'] + '?rapido=1', timeout=30) as response:
                    payload = json.load(response)
                    if response.status != 200:
                        raise ValueError('HTTP diferente de 200')
                expected = row['item']
                found = [i for i in payload['itens'] if i['numero'] == expected['item_number'] and i['lote'] == expected['lot_number']]
                if not found or found[0]['descricao'] != server.compact(expected['description']):
                    raise ValueError('item divergente ou ausente no detalhamento')
                timings.append((time.perf_counter()-before)*1000)
            except Exception as exc:
                http_errors.append(dict(chave=row['chave'], erro=str(exc)))
        for keyword in ('cadeira', 'mesa', 'computador'):
            before = time.perf_counter()
            try:
                with urlopen(base + '/internal/opportunities?' + urlencode({'palavraChave':keyword, 'tamanhoPagina':10}), timeout=60) as response:
                    payload = json.load(response)
                    searches.append(dict(termo=keyword, http=response.status, ms=round((time.perf_counter()-before)*1000, 2), resposta=payload))
            except Exception as exc:
                searches.append(dict(termo=keyword, erro=str(exc)))
    finally:
        httpd.shutdown()
        httpd.server_close()
        worker.join(timeout=10)
    result = dict(contagens=dict(counts), totais_banco=dict(itens=totals[0], oportunidades_com_itens=totals[1]),
                  divergencias_exemplos=errors, http_detalhamento=dict(sucessos=len(timings), erros=http_errors,
                  media_ms=round(statistics.mean(timings),2) if timings else None,
                  max_ms=round(max(timings),2) if timings else None,
                  p95_ms=round(sorted(timings)[int(.95*(len(timings)-1))],2) if timings else None),
                  buscas_http=searches, amostra_origem_seed=20260910, segundos=round(time.perf_counter()-start,2))
    output = ROOT / 'data/relatorios_importacao' / ('auditoria_itens_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.json')
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k != 'buscas_http'}, ensure_ascii=True, indent=2))
    print('Relatorio: ' + str(output))


if __name__ == '__main__':
    run()
