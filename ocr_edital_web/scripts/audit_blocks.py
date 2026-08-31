"""Read-only live timings and an isolated HTTP fixture for block audits.

Run from ocr_edital_web. Fixture records, uploads and exports stay in a
TemporaryDirectory; no PNCP requests or production database writes are made.
"""

import argparse
import json
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
from etl.models import MatchResult, NormalizedOpportunity, OpportunityItem


def request(base, path, payload=None, *, form=False):
    headers = {}
    body = None
    if payload is not None:
        body = (urlencode(payload) if form else json.dumps(payload)).encode()
        headers['Content-Type'] = ('application/x-www-form-urlencoded' if form
                                   else 'application/json')
    started = time.perf_counter()
    try:
        response = urlopen(Request(base + path, data=body, headers=headers), timeout=60)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        value = json.loads(raw) if 'json' in response.headers.get('Content-Type', '') else raw
        return response.status, value, elapsed


def measure(base):
    today = datetime.now().date()
    window = {'dataInicial': today.strftime('%Y%m%d'),
              'dataFinal': (today + timedelta(days=29)).strftime('%Y%m%d'),
              'campoData': 'encerramento', 'incluirSemDataEncerramento': '1',
              'pagina': '1', 'tamanhoPagina': '10'}
    cases = [('inicio', '/'), ('templates', '/api/templates'),
             ('responsaveis', '/api/responsaveis'), ('negocios_lista', '/api/negocios')]
    for name, extra in [('busca_ampla', {}), ('busca_cadeira', {'palavraChave': 'cadeira'}),
                        ('busca_uf_sp', {'uf': 'SP'}),
                        ('busca_pagina_2', {'pagina': '2'})]:
        cases.append((name, '/internal/opportunities?' + urlencode(window | extra)))
    cases.append(('itens_locais', '/identify-items?' + urlencode({
        'pncp_link': 'https://pncp.gov.br/app/editais/01612623000188/2026/15'})))
    _, businesses, _ = request(base, '/api/negocios')
    if businesses.get('negocios'):
        cases.append(('negocio_detalhe', '/api/negocios/'+businesses['negocios'][0]['id']))
    _, listing, _ = request(base, '/internal/opportunities?' + urlencode(window | {'palavraChave':'cadeira'}))
    candidate = next((item for item in listing.get('results', []) if item.get('itensIndexados')), None)
    if candidate:
        cases.append(('oportunidade_detalhe', '/internal/opportunities/'+candidate['id']))
    result = {'date': datetime.now().isoformat(), 'base_url': base,
              'method': '3 sequential requests; first/min/median/max, not a load test', 'cases': []}
    for name, path in cases:
        samples, statuses, counts = [], [], []
        for _ in range(3):
            status, data, elapsed = request(base, path)
            samples.append(elapsed)
            statuses.append(status)
            collection = next((data[key] for key in ('items', 'negocios', 'templates', 'responsaveis')
                               if key in data), []) if isinstance(data, dict) else []
            counts.append(data.get('total', len(collection)) if isinstance(data, dict) else None)
        row = {'name': name, 'path': path, 'ms': samples, 'status': statuses,
               'counts': counts, 'first_ms': samples[0], 'min_ms': min(samples),
               'median_ms': statistics.median(samples), 'max_ms': max(samples)}
        result['cases'].append(row)
        print(json.dumps(row), flush=True)
    return result


@contextmanager
def fixture():
    with tempfile.TemporaryDirectory(prefix='toth_audit_') as temporary:
        root = Path(temporary)
        with patch.multiple(server, DATA_DIR=root, DATABASE_PATH=root / 'audit.sqlite3',
                            UPLOAD_DIR=root / 'uploads', OUTPUT_DIR=root / 'outputs',
                            PREVIEW_DIR=root / 'previews', ALLOW_DETAIL_DOCUMENT_ON_DEMAND=False,
                            ALLOW_DETAIL_ITEMS_ON_DEMAND=False,
                            ALLOW_BLOCO2_ON_DEMAND_ENRICHMENT=False), \
             patch.object(server, 'list_pncp_files', return_value=[]), \
             patch.object(server, 'request_json', side_effect=RuntimeError('QA external network disabled')):
            server.ensure_dirs()
            server.init_database()
            repository = server.etl_repository()
            run = repository.create_run('pncp', 'audit_fixture', {})
            today = datetime.now().date().isoformat()
            ids = []
            for sequence in range(1, 25):
                cnpj = '12345678000199'
                link = server.pncp_app_link(cnpj, 2026, sequence)
                item_name = 'Cadeira estofada' if sequence % 2 else 'Mesa de escritorio'
                row = NormalizedOpportunity(
                    external_key=f'QA-{sequence}', source='pncp',
                    title=f'QA {sequence:03d}/2026', description='Material de escritorio para auditoria',
                    pncp_control_number=f'{cnpj}-1-{sequence:06d}/2026',
                    source_cnpj=cnpj, buyer_cnpj=cnpj, year=2026, sequence=sequence,
                    buyer_name='ORGAO FICTICIO QA', city='Cidade QA', uf='SP' if sequence % 2 else 'RJ',
                    modality='Pregao Eletronico', modality_code=6, status='Divulgada',
                    published_at=today+'T08:00:00', proposal_start_at=today+'T09:00:00',
                    proposal_end_at=today+'T23:59:00', detail_url=link, source_url=link,
                    items=[OpportunityItem(source_item_id=f'{sequence}-1', item_number='1',
                                           title=item_name, description=f'{item_name} - edital QA {sequence:03d}',
                                           quantity=2, unit='UN', estimated_unit_value=100),
                           OpportunityItem(source_item_id=f'{sequence}-2', item_number='2',
                                           title='Armario', description=f'Armario - edital QA {sequence:03d}',
                                           quantity=3, unit='UN', estimated_unit_value=200)])
                _, identifier = repository.persist_record(run_id=run, source_endpoint='fixture',
                    request_url=link, raw_payload={}, opportunity=row, match=MatchResult())
                ids.append(identifier)
            repository.finish_run(run, status='success', counters={
                'fetched':24,'inserted':24,'updated':0,'skipped':0,'failed':0})
            yield ids


def isolated_checks(base, ids):
    results = []

    def record(name, passed, **data):
        row = {'name': name, 'passed': bool(passed), **data}
        results.append(row)
        print(json.dumps(row), flush=True)

    status, page, ms = request(base, '/internal/opportunities?tamanhoPagina=10&pagina=1')
    _, page2, _ = request(base, '/internal/opportunities?tamanhoPagina=10&pagina=2')
    record('pagination', status == 200 and page['total'] == 24 and page['total_pages'] == 3
           and not ({x['id'] for x in page['results']} & {x['id'] for x in page2['results']}), ms=ms)
    _, filtered, ms = request(base, '/internal/opportunities?palavraChave=cadeira&uf=SP')
    record('keyword_in_items_and_uf', filtered['total'] == 12, ms=ms, count=filtered['total'])
    _, detail, ms = request(base, '/internal/opportunities/'+ids[0])
    record('detail_local', len(detail['itens']) == 2, ms=ms)
    selected = detail['itens'][:1]
    status, business, ms = request(base, '/internal/opportunities/'+ids[0]+'/convert-to-proposal', {'itens':selected})
    business_id = business['negocio']['id']
    _, saved, _ = request(base, '/api/negocios/'+business_id)
    record('selection_to_business', status in (200, 201) and len(saved['negocio']['itens']) == 1,
           status=status, item_count=len(saved['negocio']['itens']), ms=ms)
    _, imported, _ = request(base, '/internal/opportunities/'+ids[0]+'/convert-to-proposal', {'itens':selected})
    _, businesses, _ = request(base, '/api/negocios')
    record('business_import_idempotent', imported['negocio']['id'] == business_id and len(businesses['negocios']) == 1)

    _, template_data, _ = request(base, '/api/templates')
    template = template_data['templates'][0]['id']
    link = detail['oportunidade']['link_pncp']
    status, processed, ms = request(base, '/process', {
        'pncp_link':link, 'responsible_id':'1', 'wanted_items':'1', 'template_choice':template}, form=True)
    record('proposal_process_local', status == 200 and len(processed['items']) == 1, ms=ms)
    _, structure, ms = request(base, '/api/docx-structure', {'template_ref':processed['template_ref']})
    record('template_structure', bool(structure['nodes']), ms=ms)
    item = dict(processed['items'][0], valor_unitario='10,00', valor_total='20,00', marca='QA')
    generation = {'items':[item], 'template_ref':processed['template_ref'],
                  'source_name':'AUDIT_COLLISION', 'responsible_id':'1', 'commercial_terms':{}}
    # Freeze only the export filename clock; the HTTP and monotonic clocks stay real.
    real_clock = server.time
    class FilenameClock:
        @staticmethod
        def time():
            return 1800000000.5

        def __getattr__(self, name):
            return getattr(real_clock, name)
    with patch.object(server, 'time', FilenameClock()):
        status, export1, ms = request(base, '/generate', generation)
        record('proposal_export', status == 200, ms=ms)
        _, bytes1, _ = request(base, export1['download_url'])
        generation['items'][0]['descricao'] = 'SEGUNDA VERSAO QA'
        _, export2, _ = request(base, '/generate', generation)
        _, bytes_after, _ = request(base, export1['download_url'])
        record('immutable_proposal_downloads', export1['filename'] != export2['filename'] and bytes1 == bytes_after,
               first_filename=export1['filename'], second_filename=export2['filename'],
               original_download_changed=bytes1 != bytes_after)

    began = time.perf_counter()
    status, job, _ = request(base, '/catalog-generator/jobs', {'pncp_link':link, 'selected_item_keys':['1']})
    deadline = time.monotonic()+10
    while job['status'] in ('queued','processing') and time.monotonic()<deadline:
        time.sleep(.05)
        _, job, _ = request(base, '/catalog-generator/jobs/'+job['id'])
    record('catalog_job_selection', status == 202 and job['status']=='ready'
           and len(job['result']['items'])==1, ms=round((time.perf_counter()-began)*1000,2))
    status, exported, ms = request(base, '/catalog-generator/jobs/'+job['id']+'/export', {'items':job['result']['items']})
    record('catalog_exports', status==200 and {'xlsx','csv','json','pdf'} <= set(exported.get('exports',{})),
           ms=ms, formats=list(exported.get('exports',{})))
    revised_items = [dict(job['result']['items'][0], descricao='', quantidade='')]
    status, invalid_export, _ = request(base, '/catalog-generator/jobs/'+job['id']+'/export', {'items':revised_items})
    record('catalog_revalidates_edited_required_fields', status == 422
           or invalid_export.get('validation', {}).get('incompletos', 0) > 0,
           status=status, validation=invalid_export.get('validation'))
    long_description = 'Descricao tecnica detalhada. ' * 45 + 'SENTINELA_FINAL_QA'
    revised_items = [dict(job['result']['items'][0], descricao=long_description)]
    _, long_export, _ = request(base, '/catalog-generator/jobs/'+job['id']+'/export', {'items':revised_items})
    pdf_path = server.OUTPUT_DIR / long_export['exports']['pdf']['filename']
    with server.pdfplumber.open(pdf_path) as pdf:
        pdf_text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    record('catalog_pdf_preserves_full_description', 'SENTINELA_FINAL_QA' in pdf_text,
           description_length=len(long_description), sentinel_present='SENTINELA_FINAL_QA' in pdf_text)
    for path, payload in [('/catalog-generator/jobs', {'pncp_link':link,'selected_item_keys':[]}),
                          ('/api/docx-structure', {'template_ref':'missing.docx'})]:
        status, _, ms = request(base, path, payload)
        record('validation_'+path, 400 <= status < 500, status=status, ms=ms)

    entered = threading.Event()
    with server.CACHE_LOCK:
        server.BUSINESS_FILE_CACHE.clear()
    def slow_files(*_args):
        entered.set()
        time.sleep(1)
        return []
    with patch.object(server, 'list_pncp_files', side_effect=slow_files):
        worker = threading.Thread(target=server.get_business, args=(business_id, True))
        worker.start()
        if not entered.wait(5):
            raise RuntimeError('Lock probe did not enter document request')
        began = time.perf_counter()
        server.list_responsibles()
        delay = round((time.perf_counter()-began)*1000,2)
        worker.join(5)
        record('unrelated_db_read_not_blocked_by_remote_io', delay < 250,
               injected_remote_ms=1000, unrelated_read_ms=delay)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['measure','checks','serve','catalog-live','coverage'])
    parser.add_argument('--base-url', default='http://127.0.0.1:8765')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--delay-process', type=float, default=0)
    parser.add_argument('--delay-online', type=float, default=0)
    parser.add_argument('--delay-generate', type=float, default=0)
    parser.add_argument('--delay-catalog-export', type=float, default=0)
    parser.add_argument('--lifetime', type=int, default=1800)
    args = parser.parse_args()
    if args.mode == 'measure':
        result = measure(args.base_url)
    elif args.mode == 'coverage':
        with sqlite3.connect(server.DATABASE_PATH.resolve().as_uri()+'?mode=ro', uri=True) as connection:
            connection.execute('PRAGMA query_only=ON')
            result = {
                'opportunities':connection.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0],
                'items':connection.execute('SELECT COUNT(*) FROM opportunity_items').fetchone()[0],
                'opportunities_with_items':connection.execute(
                    'SELECT COUNT(DISTINCT opportunity_id) FROM opportunity_items').fetchone()[0],
                'today':datetime.now().date().isoformat(),
            }
            result['open_with_end_date'], result['open_with_items'] = connection.execute(
                "SELECT COUNT(*), SUM(EXISTS(SELECT 1 FROM opportunity_items i WHERE i.opportunity_id=o.id)) "
                "FROM opportunities o WHERE proposal_end_at >= ?", (datetime.now().isoformat(),)).fetchone()
        print(json.dumps(result), flush=True)
    elif args.mode == 'catalog-live':
        began = time.perf_counter()
        status, job, submission_ms = request(args.base_url, '/catalog-generator/jobs', {
            'pncp_link':'https://pncp.gov.br/app/editais/01612623000188/2026/15',
            'selected_item_keys':['1']})
        print(json.dumps({'job_id':job.get('id'),'status':status,'submission_ms':submission_ms}), flush=True)
        deadline = time.monotonic()+90
        while job.get('status') in ('queued','processing') and time.monotonic()<deadline:
            time.sleep(1)
            _, job, _ = request(args.base_url, '/catalog-generator/jobs/'+job['id'])
        result = {'job_id':job.get('id'),'status':job.get('status'),'stage':job.get('stage'),
                  'elapsed_ms':round((time.perf_counter()-began)*1000,2),'submission_ms':submission_ms,
                  'poll_interval_ms':1000, 'items':len((job.get('result') or {}).get('items',[])),
                  'warnings':(job.get('result') or {}).get('warnings',[]), 'error':job.get('error')}
        print(json.dumps(result), flush=True)
    else:
        with fixture() as ids:
            class AuditHandler(server.App):
                def log_message(self, *_args):
                    pass

                def do_POST(self):
                    request_path = urlparse(self.path).path
                    if request_path == '/process':
                        time.sleep(args.delay_process)
                    if request_path == '/generate':
                        time.sleep(args.delay_generate)
                    if request_path.endswith('/export'):
                        time.sleep(args.delay_catalog_export)
                    super().do_POST()

                def do_GET(self):
                    if urlparse(self.path).path == '/pncp-search':
                        time.sleep(args.delay_online)
                        server.json_response(self, 200, {
                            'results':[], 'total':0, 'searching':False, 'complete':False,
                            'reconciliation':{'inserted':0,'updated':0,'status':'partial'}})
                        return
                    super().do_GET()

            httpd = ThreadingHTTPServer(('127.0.0.1',0), AuditHandler)
            httpd.daemon_threads = True
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            base = 'http://127.0.0.1:'+str(httpd.server_port)
            print(json.dumps({'fixture_url':base,'database':str(server.DATABASE_PATH),'ids':ids[:2]}), flush=True)
            try:
                result = isolated_checks(base, ids) if args.mode=='checks' else None
                if args.mode=='serve':
                    time.sleep(args.lifetime)
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
