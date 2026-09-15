"""Bounded read-only database and local API audit; no external enrichment."""

import json
import sqlite3
import statistics
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / 'data/pncp.sqlite3'
REPORT = ROOT / 'reports/live-database-2026-09-12.json'
report = {'started_at': datetime.now().astimezone().isoformat(), 'database': str(DATABASE),
          'database_bytes': DATABASE.stat().st_size, 'checks': {}, 'api': []}


def checkpoint():
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')


def check(name, sql, params=(), seconds=60):
    started = time.perf_counter()
    with sqlite3.connect(DATABASE.resolve().as_uri() + '?mode=ro', uri=True, timeout=5) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.set_progress_handler(lambda: int(time.perf_counter() - started > seconds), 10000)
        try:
            value = {'rows': [dict(row) for row in db.execute(sql, params)]}
        except sqlite3.Error as exc:
            value = {'error': str(exc), 'timeout_seconds': seconds}
    value['seconds'] = round(time.perf_counter() - started, 3)
    report['checks'][name] = value
    print(name, json.dumps(value, ensure_ascii=True)[:1800], flush=True)
    checkpoint()
    return value.get('rows', [])


def request(name, path):
    started = time.perf_counter()
    row = {'name': name, 'path': path}
    data = None
    try:
        with urlopen('http://127.0.0.1:8765' + path, timeout=20) as response:
            raw = response.read()
            row.update(status=response.status, bytes=len(raw))
            if 'json' in response.headers.get('Content-Type', ''):
                data = json.loads(raw)
                if isinstance(data, dict):
                    row['keys'] = list(data)
                    row['total'] = data.get('total')
    except Exception as exc:
        row['error'] = str(exc)
    row['ms'] = round((time.perf_counter() - started) * 1000, 2)
    report['api'].append(row)
    checkpoint()
    return data


def status():
    return json.loads((ROOT / 'data/items_enrichment_priority.status.json').read_text(encoding='utf-8'))


report['extraction_before'] = status()
check('journal', 'PRAGMA journal_mode')
check('counts', '''SELECT (SELECT count(*) FROM opportunities) AS opportunities,
    (SELECT count(*) FROM opportunity_items) AS items,
    (SELECT count(*) FROM opportunity_search_docsize) AS search_entries''')
check('coverage', '''SELECT source, count(*) AS opportunities,
    sum(EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)) AS with_items,
    max(published_at) AS latest_publication FROM opportunities o GROUP BY source''')
check('month_coverage', '''SELECT count(*) AS opportunities,
    sum(EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)) AS with_items,
    sum(object_matches_material=1) AS classified_material,
    sum(object_matches_material=1 AND NOT EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)) AS material_without_items
    FROM opportunities o WHERE published_at >= ? AND published_at < ?''',
      (datetime.now().strftime('%Y-%m-01'), datetime.now().strftime('%Y-%m-%d') + 'T23:59:59'))
check('indexes', "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index' AND tbl_name IN ('opportunities','opportunity_items')")
check('recent_runs', '''SELECT id,source,run_type,status,started_at,updated_at,total_fetched,
    total_updated,total_failed,error_message FROM etl_runs ORDER BY started_at DESC LIMIT 8''')
check('quick_check', 'PRAGMA quick_check(10)', seconds=120)
sample = check('sample', '''SELECT o.rowid AS search_rowid,o.id,o.external_key
    FROM opportunities o WHERE EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)
    ORDER BY o.published_at DESC LIMIT 50''')
sample_errors = []
sample_items = 0
with sqlite3.connect(DATABASE.resolve().as_uri() + '?mode=ro', uri=True, timeout=5) as db:
    for opportunity in sample:
        indexed = db.execute('SELECT content FROM opportunity_search WHERE rowid=?', (opportunity['search_rowid'],)).fetchone()
        items = db.execute('SELECT source_item_id,description FROM opportunity_items WHERE opportunity_id=?', (opportunity['id'],)).fetchall()
        sample_items += len(items)
        keys = [row[0] for row in items if row[0]]
        failures = []
        if len(keys) != len(set(keys)):
            failures.append('duplicate_source_item_id')
        if not indexed:
            failures.append('missing_search_row')
        elif any(text and text not in indexed[0] for _, text in items):
            failures.append('description_missing_from_search_content')
        if any(not (text or '').strip() for _, text in items):
            failures.append('empty_description')
        if failures:
            sample_errors.append({'id': opportunity['id'], 'failures': failures})
report['sample_validation'] = {'opportunities': len(sample), 'items': sample_items, 'errors': sample_errors}
for name, path in [('app','/'), ('templates','/api/templates'), ('responsibles','/api/responsaveis'),
                   ('businesses','/api/negocios'), ('kanban','/api/kanban')]:
    for _ in range(3):
        request(name, path)
window = {'campoData': 'publicacao', 'dataInicial': datetime.now().strftime('%Y%m01'),
          'dataFinal': datetime.now().strftime('%Y%m%d'), 'pagina': '1', 'tamanhoPagina': '50'}
for name, extra in [('search',{}), ('keyword',{'palavraChave':'cadeira'}), ('uf',{'uf':'SP'})]:
    for _ in range(3):
        request(name, '/internal/opportunities?' + urlencode(window | extra))
for opportunity in sample:
    request('detail_local', '/internal/opportunities/' + opportunity['id'] + '?rapido=1')
report['timings'] = {}
for name in dict.fromkeys(row['name'] for row in report['api']):
    rows = [row for row in report['api'] if row['name'] == name]
    values = sorted(row['ms'] for row in rows)
    report['timings'][name] = {'requests':len(values), 'median_ms':statistics.median(values),
        'p95_ms':values[min(len(values)-1, int(len(values)*.95))], 'max_ms':max(values),
        'errors':sum(row.get('status') != 200 for row in rows)}
report['extraction_after'] = status()
report['finished_at'] = datetime.now().astimezone().isoformat()
checkpoint()
print(json.dumps({'timings':report['timings'], 'sample':report['sample_validation'],
                  'extraction':report['extraction_after']}, indent=2), flush=True)
