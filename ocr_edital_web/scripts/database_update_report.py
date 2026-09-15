"""Generate a local progress report for publications, items and search indexing."""

import ctypes
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def process_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return None if ctypes.get_last_error() == 5 else False
        try:
            code = ctypes.c_ulong()
            return code.value == 259 if kernel.GetExitCodeProcess(handle, ctypes.byref(code)) else None
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return None


def main():
    now = datetime.now().astimezone()
    publication = json.loads((ROOT / "data/publication_update.status.json").read_text(encoding="utf-8"))
    items = json.loads((ROOT / "data/items_enrichment_priority.status.json").read_text(encoding="utf-8"))
    database = ROOT / "data/pncp.sqlite3"
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=5) as connection:
        counts = connection.execute("""SELECT
            (SELECT count(*) FROM opportunities),
            (SELECT count(*) FROM opportunity_items),
            (SELECT count(*) FROM opportunity_search_docsize),
            (SELECT count(*) FROM opportunities o LEFT JOIN opportunity_search_docsize s ON s.id=o.rowid WHERE s.id IS NULL)
        """).fetchone()
    item_alive, publication_alive = process_alive(items["pid"]), process_alive(publication["pid"])
    seconds = items.get("estimated_seconds_remaining") if item_alive else None
    forecast = (now + timedelta(seconds=seconds)).strftime("%d/%m/%Y %H:%M") if seconds else "indisponivel"
    hours = f"{seconds / 3600:.1f} horas" if seconds else "indisponivel"
    preliminary = publication.get("estimated_seconds_first_pass")
    publication_eta = f"{preliminary / 3600:.1f} horas (preliminar)" if preliminary and publication_alive else "ainda em calibracao"
    summary = {"generated_at": now.isoformat(),
               "database": {"opportunities": counts[0], "items": counts[1], "indexed_opportunities": counts[2], "missing_index": counts[3]},
               "publications": {key: value for key, value in publication.items() if key not in ("completed_units", "failed_units")},
               "publication_units_completed": len(publication["completed_units"]),
               "publication_units_failed": len(publication["failed_units"]),
               "publication_process_alive": publication_alive, "item_process_alive": item_alive,
               "items": items, "item_first_pass_forecast": forecast}
    path = ROOT / "reports/database-update-current"
    path.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    text = f"""# Atualizacao do banco Toth

Gerado em {now:%d/%m/%Y %H:%M:%S %z}.

## Funcionamento

1. Oportunidades: fila de {publication['date_from']} a {publication['date_to']}, por dia/modalidade, das datas mais recentes para as antigas. Consulta Compras.gov quando ha equivalencia e usa PNCP como alternativa. Paginas e identidades sao verificadas; unidades incompletas ficam pendentes para retomada.
2. Itens: o extrator existente consulta as oportunidades sem itens. As oportunidades inseridas pela primeira fila passam a ser elegiveis. Tres trabalhadores, com controle de tentativas e espera entre requisicoes.
3. Indexacao: os metodos do repositorio atualizam o indice textual ao gravar oportunidades e lotes de itens. O indice fica disponivel ao Bloco 1 apos o commit da transacao.

## Progresso observado

| Etapa | Situacao |
| --- | --- |
| Processo de oportunidades ativo | {publication_alive} (PID {publication['pid']}) |
| Unidades concluidas | {len(publication['completed_units'])} de {publication['total_units']} |
| Unidades com falha nesta passagem | {len(publication['failed_units'])} |
| Novas oportunidades / atualizadas nesta execucao | {publication['counters']['inserted']} / {publication['counters']['updated']} |
| Processo de itens ativo | {item_alive} (PID {items['pid']}) |
| Tentativas de itens | {items['completed']} de {items['total']} ({items['progress_percent']}%) |
| Oportunidades preenchidas / tentativas falhas | {items['counters']['updated']} / {items['counters']['failed']} |
| Itens gravados nesta execucao | {items['counters']['items']} |
| Pendencias estimadas na fila atual de itens | {items['remaining']} |
| Total de oportunidades no banco | {counts[0]} |
| Total de itens no banco | {counts[1]} |
| Entradas de oportunidade no indice | {counts[2]} |
| Oportunidades sem entrada no indice | {counts[3]} |

## Previsoes

- Primeira passagem pela fila atual de itens: cerca de {hours}, ou {forecast}, se o computador continuar ligado, conectado e no ritmo atual.
- Primeira passagem pela fila de oportunidades: {publication_eta}. Dias vazios e dias com muitas paginas possuem custos diferentes; a estimativa inicial pode variar bastante.
- Indexacao: ocorre durante a gravacao; nao existe um lote separado aguardando o fim de toda a coleta.

As previsoes sao para tentativas das filas observadas. Novas oportunidades aumentam o trabalho de itens. Falhas nao equivalem a registros concluidos com sucesso, e oportunidades com itens parcialmente existentes exigem reconciliacao especifica. Portanto nao ha prazo comprovado para cobertura integral de todos os dados externos.

O coletor de oportunidades realiza uma passagem retomavel pelo periodo configurado. Ao terminar parcial, as unidades nao concluidas permanecem no arquivo de progresso; uma nova execucao do mesmo comando retoma essas unidades. Dias posteriores a data final exigem atualizar o parametro date-to. Nao foi criado agendamento automatico nem servico de reinicio do Windows.

Para atualizar este relatorio, executar a partir de ocr_edital_web: `python scripts/database_update_report.py`.
"""
    path.with_suffix(".md").write_text(text, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    print(path.with_suffix(".md"))


if __name__ == "__main__":
    main()
