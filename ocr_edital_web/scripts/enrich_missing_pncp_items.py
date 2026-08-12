"""Fill missing PNCP items/documents for opportunities already in SQLite."""

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

from etl.classifier import OpportunityClassifier
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
    parser.add_argument("--profile-json", default="{}")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")
    if args.item_max_pages <= 0:
        raise SystemExit("--item-max-pages must be greater than zero")

    profile = _json_object(args.profile_json)
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
    classifier = OpportunityClassifier()

    run_id = repository.create_run(
        "pncp",
        "detail_enrichment",
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
                    classifier=classifier,
                    run_id=run_id,
                    row=row,
                    profile=profile,
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
                    source_endpoint="detail_enrichment",
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
        ORDER BY o.published_at ASC, o.updated_at ASC, o.id ASC
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
    classifier: OpportunityClassifier,
    run_id: str,
    row: dict[str, Any],
    profile: dict[str, Any],
    item_max_pages: int,
    dry_run: bool,
) -> tuple[str, int, int, list[str]]:
    cnpj = str(row["source_cnpj"])
    year = int(row["year"])
    sequence = int(row["sequence"])
    listing = _row_to_listing(row)
    raw_composite: dict[str, Any] = {
        "listing": listing,
        "detail": None,
        "items": [],
        "documents": [],
        "enrichment_errors": [],
    }

    items: list[dict[str, Any]] = []
    item_request_url = str(row["detail_url"] or "")
    for page in connector.iter_items(cnpj, year, sequence, item_max_pages):
        items.extend(page.records)
        raw_composite["items"].append(page.raw_payload)
        item_request_url = page.request_url

    mapped_items = mapper.map_items(items)
    if not mapped_items:
        raise RuntimeError("PNCP returned no items for this opportunity")
    if not dry_run:
        # Commit items first. Detail/document instability must not discard this progress.
        repository.replace_opportunity_items(row["id"], mapped_items)

    warnings: list[str] = []
    detail = None
    try:
        detail_payload = connector.fetch_detail(cnpj, year, sequence)
        if isinstance(detail_payload.payload, dict):
            detail = detail_payload.payload
        raw_composite["detail"] = detail_payload.payload
        raw_composite["detail_request_url"] = detail_payload.request_url
    except Exception as exc:
        warning = f"detail: {exc}"
        warnings.append(warning)
        raw_composite["enrichment_errors"].append(warning)

    documents: list[dict[str, Any]] = []
    documents_fetched = False
    try:
        documents_payload = connector.fetch_documents(cnpj, year, sequence)
        documents = _extract_records(documents_payload.payload)
        documents_fetched = True
        raw_composite["documents"] = documents_payload.payload
        raw_composite["documents_request_url"] = documents_payload.request_url
    except Exception as exc:
        warning = f"documents: {exc}"
        warnings.append(warning)
        raw_composite["enrichment_errors"].append(warning)

    opportunity = mapper.map(listing, detail=detail, items=items, documents=documents)
    match = classifier.classify(opportunity, profile)
    if dry_run:
        outcome = repository.preview_upsert(opportunity)
    else:
        outcome, _ = repository.persist_record(
            run_id=run_id,
            source_endpoint="detail_enrichment",
            request_url=item_request_url,
            raw_payload=raw_composite,
            opportunity=opportunity,
            match=match,
            replace_children=False,
        )
        if documents_fetched:
            repository.replace_opportunity_documents(row["id"], opportunity.documents)
    return outcome, len(mapped_items), len(opportunity.documents), warnings


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


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "content", "results", "resultado"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []


def _json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"--profile-json must contain valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit("--profile-json must contain a JSON object")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
