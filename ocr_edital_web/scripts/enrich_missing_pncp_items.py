"""Fill missing PNCP items for opportunities already stored in SQLite."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.connectors import HttpJsonClient, PNCPConnector
from etl.mappers import PNCPMapper
from etl.repository import ETLRepository


DEFAULT_DATABASE = PROJECT_ROOT / "data" / "pncp.sqlite3"
DEFAULT_DATE_FROM = "2026-07-01"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--request-delay", type=float, default=2.0)
    parser.add_argument("--between-delay", type=float, default=1.0)
    parser.add_argument("--item-max-pages", type=int, default=20)
    parser.add_argument("--profile-json", default="{}", help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")
    if args.item_max_pages <= 0:
        raise SystemExit("--item-max-pages must be greater than zero")

    repository = ETLRepository(args.database)
    repository.initialize()
    connector = PNCPConnector(
        client=HttpJsonClient(
            timeout=args.timeout,
            retries=args.retries,
            request_delay=args.request_delay,
        )
    )
    mapper = PNCPMapper()

    run_id = repository.create_run(
        "pncp",
        "item_enrichment_batch",
        {
            "date_from": args.date_from,
            "limit": args.limit,
            "dry_run": args.dry_run,
            "item_max_pages": args.item_max_pages,
        },
    )
    counters = {
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "items": 0,
        "documents": 0,
    }

    try:
        rows = _load_missing(repository, args.date_from, args.limit)
        for index, row in enumerate(rows, 1):
            counters["fetched"] += 1
            try:
                outcome, item_count, document_count, warnings = _enrich_one(
                    repository=repository,
                    connector=connector,
                    mapper=mapper,
                    run_id=run_id,
                    row=row,
                    item_max_pages=args.item_max_pages,
                    dry_run=args.dry_run,
                )
                counters[outcome] += 1
                counters["items"] += item_count
                counters["documents"] += document_count
                print(
                    json.dumps(
                        {
                            "index": index,
                            "total_loaded": len(rows),
                            "opportunity_id": row["id"],
                            "external_key": row["external_key"],
                            "outcome": outcome,
                            "items": item_count,
                            "documents": document_count,
                            "warnings": warnings,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                counters["failed"] += 1
                repository.save_failed_source_record(
                    run_id=run_id,
                    source="pncp",
                    source_endpoint="item_enrichment_batch",
                    request_url=str(row["detail_url"] or ""),
                    raw_payload=_row_to_listing(row),
                    error_message=str(exc),
                    external_key=row["external_key"],
                )
                print(
                    json.dumps(
                        {
                            "index": index,
                            "total_loaded": len(rows),
                            "opportunity_id": row["id"],
                            "external_key": row["external_key"],
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            repository.update_run_progress(run_id, counters)
            if args.between_delay and index < len(rows):
                time.sleep(args.between_delay)
    except Exception as exc:
        repository.finish_run(run_id, status="failed", counters=counters, error_message=str(exc))
        raise

    status = "dry_run" if args.dry_run else ("partial" if counters["failed"] else "success")
    repository.finish_run(run_id, status=status, counters=counters)
    print(json.dumps({"run_id": run_id, "status": status, **counters}, ensure_ascii=False, indent=2))
    return 0 if counters["failed"] == 0 else 2


def _load_missing(repository: ETLRepository, date_from: str, limit: int | None) -> list[dict[str, Any]]:
    sql = """
        SELECT o.*
        FROM opportunities o
        WHERE substr(coalesce(o.published_at, ''), 1, 10) >= ?
          AND o.source_cnpj IS NOT NULL
          AND o.year IS NOT NULL
          AND o.sequence IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM opportunity_items i WHERE i.opportunity_id = o.id
          )
        ORDER BY o.published_at DESC, o.updated_at ASC, o.id ASC
    """
    params: list[Any] = [date_from]
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with repository.connect() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _enrich_one(
    *,
    repository: ETLRepository,
    connector: PNCPConnector,
    mapper: PNCPMapper,
    run_id: str,
    row: dict[str, Any],
    item_max_pages: int,
    dry_run: bool,
) -> tuple[str, int, int, list[str]]:
    cnpj = str(row["source_cnpj"])
    year = int(row["year"])
    sequence = int(row["sequence"])
    items: list[dict[str, Any]] = []
    item_request_url = str(row["detail_url"] or "")
    page_count = 0
    for page in connector.iter_items(cnpj, year, sequence, item_max_pages):
        items.extend(page.records)
        page_count += 1
        item_request_url = page.request_url

    mapped_items = mapper.map_items(items)
    if not mapped_items:
        raise RuntimeError("PNCP returned no items for this opportunity")
    if dry_run:
        outcome = "updated"
    else:
        persistence = repository.persist_opportunity_items_enrichment(
            run_id=run_id,
            opportunity_id=row["id"],
            items=mapped_items,
            request_url=item_request_url,
            audit_summary={
                "pages_received": page_count,
                "items_received": len(items),
                "items_normalized": len(mapped_items),
                "mode": "items_only_batch",
            },
            external_key=row["external_key"],
            finish_run=False,
        )
        outcome = "updated" if persistence["persisted"] else "skipped"
    return outcome, len(mapped_items), 0, []


def _row_to_listing(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "numeroControlePNCP": row["pncp_control_number"],
        "numeroCnpj": row["source_cnpj"],
        "anoCompra": row["year"],
        "sequencialCompra": row["sequence"],
        "numeroCompra": row["process_number"] or row["title"],
        "processo": row["process_number"],
        "objetoCompra": row["description"] or row["title"],
        "orgaoEntidade": {
            "cnpj": row["buyer_cnpj"],
            "razaoSocial": row["buyer_name"],
        },
        "unidadeOrgao": {
            "ufSigla": row["uf"],
            "municipioNome": row["city"],
            "codigoUnidade": row["uasg"],
        },
        "modalidadeNome": row["modality"],
        "modalidadeId": row["modality_code"],
        "situacaoCompraNome": row["status"],
        "valorTotalEstimado": row["estimated_value"],
        "dataPublicacaoPncp": row["published_at"],
        "dataAberturaProposta": row["proposal_start_at"],
        "dataEncerramentoProposta": row["proposal_end_at"],
        "linkSistemaOrigem": row["origin_url"] or row["source_url"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
