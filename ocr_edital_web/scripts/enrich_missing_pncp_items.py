"""Fill missing PNCP items for opportunities already stored in SQLite."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.connectors import HttpJsonClient, PNCPConnector
from etl.mappers import PNCPMapper
from etl.repository import ETLRepository


DEFAULT_DATABASE = PROJECT_ROOT / "data" / "pncp.sqlite3"
DEFAULT_DATE_FROM = "2026-06-01"
DEFAULT_STATUS_FILE = PROJECT_ROOT / "data" / "items_enrichment_priority.status.json"
DEFAULT_PID_FILE = PROJECT_ROOT / "data" / "items_enrichment_priority.pid"


class RequestPacer:
    """Space requests globally even when multiple workers are active."""

    def __init__(self, interval: float) -> None:
        self.interval = max(float(interval), 0.0)
        self._lock = threading.Lock()
        self._next_request_at = 0.0

    def wait(self) -> None:
        if not self.interval:
            return
        with self._lock:
            now = time.monotonic()
            scheduled_at = max(now, self._next_request_at)
            self._next_request_at = scheduled_at + self.interval
        delay = scheduled_at - now
        if delay > 0:
            time.sleep(delay)


class PacedHttpJsonClient(HttpJsonClient):
    def __init__(self, *, pacer: RequestPacer, **kwargs: Any) -> None:
        super().__init__(request_delay=0, **kwargs)
        self.pacer = pacer

    def get(self, url, params=None):
        self.pacer.wait()
        return super().get(url, params)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM)
    parser.add_argument("--date-to")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument(
        "--scope",
        choices=("open-future", "publication", "opening", "closing"),
        default="publication",
    )
    parser.add_argument(
        "--source",
        choices=("all", "pncp", "comprasgov"),
        default="all",
        help="Limit stored opportunities by source; items still come from PNCP.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Maximum opportunities loaded and submitted at once.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=1.0)
    parser.add_argument("--request-delay", type=float, default=0.5)
    parser.add_argument("--between-delay", type=float, default=0.0)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--retry-failures-after-hours", type=float, default=12.0)
    parser.add_argument("--item-page-size", type=int, default=500)
    parser.add_argument("--item-max-pages", type=int, default=20)
    parser.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--profile-json", default="{}", help=argparse.SUPPRESS)
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Report the eligible queue without writing to SQLite or calling an API.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        raise SystemExit("--limit must be greater than zero")
    if not 1 <= args.batch_size <= 2000:
        raise SystemExit("--batch-size must be between 1 and 2000")
    if args.item_max_pages <= 0:
        raise SystemExit("--item-max-pages must be greater than zero")
    if not 1 <= args.item_page_size <= 500:
        raise SystemExit("--item-page-size must be between 1 and 500")
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    if args.request_delay < 0 or args.between_delay < 0:
        raise SystemExit("request delays cannot be negative")
    if args.retry_failures_after_hours < 0:
        raise SystemExit("--retry-failures-after-hours cannot be negative")
    args.date_to = args.date_to or args.as_of
    try:
        parsed_date_from = date.fromisoformat(args.date_from)
        parsed_date_to = date.fromisoformat(args.date_to)
        date.fromisoformat(args.as_of)
    except ValueError as exc:
        raise SystemExit("dates must use YYYY-MM-DD") from exc
    if parsed_date_from > parsed_date_to:
        raise SystemExit("--date-from must be earlier than or equal to --date-to")

    repository = ETLRepository(args.database)
    if args.plan:
        database_path = Path(args.database)
        if not database_path.is_file():
            raise SystemExit(f"database not found: {database_path}")
        summary = _summarize_missing(
            repository,
            args.date_from,
            scope=args.scope,
            source=args.source,
            date_to=args.date_to,
            as_of=args.as_of,
            retry_failures_after_hours=args.retry_failures_after_hours,
        )
        sample_limit = min(args.limit or 10, 100)
        sample = _load_missing(
            repository,
            args.date_from,
            sample_limit,
            scope=args.scope,
            source=args.source,
            date_to=args.date_to,
            as_of=args.as_of,
            retry_failures_after_hours=args.retry_failures_after_hours,
        )
        print(json.dumps({
            "mode": "plan",
            "database": str(database_path.resolve()),
            "filters": {
                "date_from": args.date_from,
                "date_to": args.date_to,
                "as_of": args.as_of,
                "scope": args.scope,
                "source": args.source,
                "retry_failures_after_hours": args.retry_failures_after_hours,
            },
            "queue": summary,
            "sample": [
                {
                    "opportunity_id": row["id"],
                    "external_key": row["external_key"],
                    "source": row["source"],
                    "priority": row["priority"],
                    "published_at": row["published_at"],
                    "proposal_start_at": row["proposal_start_at"],
                    "proposal_end_at": row["proposal_end_at"],
                }
                for row in sample
            ],
        }, ensure_ascii=False, indent=2))
        return 0

    status_path = Path(args.status_file) if args.status_file else None
    pid_path = Path(args.pid_file) if args.pid_file else None
    with _exclusive_process(pid_path):
        repository.initialize()
        return _run_enrichment(args, repository, status_path)


def _run_enrichment(
    args: argparse.Namespace,
    repository: ETLRepository,
    status_path: Path | None,
) -> int:
    pacer = RequestPacer(args.request_delay)
    worker_state = threading.local()

    def worker_dependencies() -> tuple[PNCPConnector, PNCPMapper]:
        connector = getattr(worker_state, "connector", None)
        mapper = getattr(worker_state, "mapper", None)
        if connector is None:
            connector = PNCPConnector(
                client=PacedHttpJsonClient(
                    pacer=pacer,
                    timeout=args.timeout,
                    retries=args.retries,
                    retry_backoff=args.retry_backoff,
                ),
                page_size=args.item_page_size,
            )
            worker_state.connector = connector
        if mapper is None:
            mapper = PNCPMapper()
            worker_state.mapper = mapper
        return connector, mapper

    run_id = repository.create_run(
        "pncp",
        "item_enrichment_batch",
        {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "as_of": args.as_of,
            "scope": args.scope,
            "source": args.source,
            "limit": args.limit,
            "batch_size": args.batch_size,
            "dry_run": args.dry_run,
            "workers": args.workers,
            "request_delay": args.request_delay,
            "retry_failures_after_hours": args.retry_failures_after_hours,
            "item_max_pages": args.item_max_pages,
            "item_page_size": args.item_page_size,
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
    started_at = datetime.now().astimezone()
    queue = _summarize_missing(
        repository,
        args.date_from,
        scope=args.scope,
        source=args.source,
        date_to=args.date_to,
        as_of=args.as_of,
        retry_failures_after_hours=args.retry_failures_after_hours,
    )
    total = min(queue["total"], args.limit) if args.limit is not None else queue["total"]
    if args.dry_run:
        total = min(total, args.batch_size)

    try:
        _write_status(
            status_path,
            _status_payload(run_id, args, counters, total, started_at, "running"),
        )

        def enrich(row):
            connector, mapper = worker_dependencies()
            return _enrich_one(
                repository=repository,
                connector=connector,
                mapper=mapper,
                run_id=run_id,
                row=row,
                item_max_pages=args.item_max_pages,
                dry_run=args.dry_run,
            )

        remaining_limit = total if args.dry_run else args.limit
        while remaining_limit is None or remaining_limit > 0:
            load_limit = args.batch_size
            if remaining_limit is not None:
                load_limit = min(load_limit, remaining_limit)
            rows = _load_missing(
                repository,
                args.date_from,
                load_limit,
                scope=args.scope,
                source=args.source,
                date_to=args.date_to,
                as_of=args.as_of,
                retry_failures_after_hours=args.retry_failures_after_hours,
            )
            if not rows:
                break

            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {executor.submit(enrich, row): row for row in rows}
                for future in as_completed(futures):
                    row = futures[future]
                    counters["fetched"] += 1
                    message = {
                        "index": counters["fetched"],
                        "total_target": total,
                        "batch_loaded": len(rows),
                        "priority": row.get("priority"),
                        "opportunity_id": row["id"],
                        "external_key": row["external_key"],
                    }
                    try:
                        outcome, item_count, document_count, warnings = future.result()
                        counters[outcome] += 1
                        counters["items"] += item_count
                        counters["documents"] += document_count
                        message.update({
                            "outcome": outcome,
                            "items": item_count,
                            "documents": document_count,
                            "warnings": warnings,
                        })
                    except Exception as exc:
                        counters["failed"] += 1
                        if not args.dry_run:
                            repository.save_failed_source_record(
                                run_id=run_id,
                                source="pncp",
                                source_endpoint="item_enrichment_batch",
                                request_url=str(row["detail_url"] or ""),
                                raw_payload=_row_to_listing(row),
                                error_message=str(exc),
                                external_key=row["external_key"],
                            )
                        message["error"] = str(exc)
                    print(json.dumps(message, ensure_ascii=False), flush=True)
                    try:
                        repository.update_run_progress(run_id, counters)
                    except Exception as exc:
                        print(
                            json.dumps({"progress_warning": str(exc)}, ensure_ascii=False),
                            file=sys.stderr,
                            flush=True,
                        )
                    try:
                        _write_status(
                            status_path,
                            _status_payload(
                                run_id, args, counters, total, started_at, "running"
                            ),
                        )
                    except OSError as exc:
                        print(
                            json.dumps({"status_warning": str(exc)}, ensure_ascii=False),
                            file=sys.stderr,
                            flush=True,
                        )
                    if args.between_delay and counters["fetched"] < total:
                        time.sleep(args.between_delay)

            if remaining_limit is not None:
                remaining_limit -= len(rows)
            if args.dry_run:
                break
    except Exception as exc:
        repository.finish_run(run_id, status="failed", counters=counters, error_message=str(exc))
        _write_status(
            status_path,
            _status_payload(
                run_id, args, counters, counters["fetched"], started_at, "failed", str(exc)
            ),
        )
        raise

    status = "dry_run" if args.dry_run else ("partial" if counters["failed"] else "success")
    repository.finish_run(run_id, status=status, counters=counters)
    _write_status(
        status_path,
        _status_payload(run_id, args, counters, total, started_at, status),
    )
    print(json.dumps({"run_id": run_id, "status": status, **counters}, ensure_ascii=False, indent=2))
    return 0 if counters["failed"] == 0 else 2


def _status_payload(
    run_id: str,
    args: argparse.Namespace,
    counters: dict[str, int],
    total: int,
    started_at: datetime,
    status: str,
    error: str = "",
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    elapsed_seconds = max((now - started_at).total_seconds(), 0.001)
    completed = int(counters.get("fetched") or 0)
    rate = completed / elapsed_seconds
    remaining = max(total - completed, 0)
    return {
        "run_id": run_id,
        "pid": os.getpid(),
        "status": status,
        "scope": args.scope,
        "source": args.source,
        "date_from": args.date_from,
        "date_to": args.date_to,
        "as_of": args.as_of,
        "total": total,
        "completed": completed,
        "remaining": remaining,
        "progress_percent": round((completed / total * 100) if total else 100.0, 2),
        "opportunities_per_minute": round(rate * 60, 2),
        "estimated_seconds_remaining": round(remaining / rate) if rate else None,
        "counters": dict(counters),
        "started_at": started_at.isoformat(),
        "updated_at": now.isoformat(),
        "error": error,
    }


def _write_status(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    last_error: OSError | None = None
    for attempt in range(5):
        try:
            temporary.write_text(serialized, encoding="utf-8")
            temporary.replace(path)
            return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1 * (attempt + 1))
    try:
        path.write_text(serialized, encoding="utf-8")
    except OSError as exc:
        print(
            json.dumps(
                {"status_warning": str(exc), "atomic_error": str(last_error)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
            flush=True,
        )


@contextmanager
def _exclusive_process(pid_path: Path | None):
    if pid_path is None:
        yield
        return

    pid_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = pid_path.with_name(f"{pid_path.name}.lock")
    lock_handle = lock_path.open("a+b")
    try:
        lock_handle.seek(0, os.SEEK_END)
        if lock_handle.tell() == 0:
            lock_handle.write(b"\0")
            lock_handle.flush()
        lock_handle.seek(0)
        try:
            _lock_handle(lock_handle)
        except OSError as exc:
            owner = "unknown"
            try:
                owner = pid_path.read_text(encoding="utf-8").strip() or owner
            except OSError:
                pass
            raise SystemExit(
                f"another item enrichment process is already running (pid {owner})"
            ) from exc

        pid_path.write_text(str(os.getpid()), encoding="utf-8")
        try:
            yield
        finally:
            try:
                if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    pid_path.unlink()
            except OSError:
                pass
            _unlock_handle(lock_handle)
    finally:
        lock_handle.close()


def _lock_handle(handle) -> None:
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_handle(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_missing(
    repository: ETLRepository,
    date_from: str,
    limit: int | None,
    *,
    scope: str = "open-future",
    source: str = "all",
    date_to: str | None = None,
    as_of: str | None = None,
    retry_failures_after_hours: float = 12.0,
) -> list[dict[str, Any]]:
    priority_sql, where_sql, params = _missing_selection(
        date_from,
        scope=scope,
        source=source,
        date_to=date_to,
        as_of=as_of,
        retry_failures_after_hours=retry_failures_after_hours,
    )
    sql = f"""
        SELECT o.*, {priority_sql} AS priority
        FROM opportunities o
        WHERE {where_sql}
        ORDER BY priority,
                 COALESCE(o.proposal_end_at, o.proposal_start_at, o.published_at) ASC,
                 CASE WHEN o.source = 'pncp' THEN 0 ELSE 1 END,
                 o.updated_at ASC,
                 o.id ASC
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    with repository.connect() as connection:
        return [dict(row) for row in connection.execute(sql, params).fetchall()]


def _summarize_missing(
    repository: ETLRepository,
    date_from: str,
    *,
    scope: str = "open-future",
    source: str = "all",
    date_to: str | None = None,
    as_of: str | None = None,
    retry_failures_after_hours: float = 12.0,
) -> dict[str, Any]:
    priority_sql, where_sql, params = _missing_selection(
        date_from,
        scope=scope,
        source=source,
        date_to=date_to,
        as_of=as_of,
        retry_failures_after_hours=retry_failures_after_hours,
    )
    sql = f"""
        SELECT source, priority, COUNT(*) AS count
        FROM (
            SELECT o.source, {priority_sql} AS priority
            FROM opportunities o
            WHERE {where_sql}
        ) pending
        GROUP BY source, priority
        ORDER BY source, priority
    """
    by_source: dict[str, int] = {}
    by_priority = {"open": 0, "future": 0, "active_unknown_start": 0, "other": 0}
    priority_names = {
        0: "open",
        1: "future",
        2: "active_unknown_start",
        3: "other",
    }
    total = 0
    with repository.connect() as connection:
        rows = connection.execute(sql, params).fetchall()
    for row in rows:
        count = int(row["count"])
        total += count
        by_source[row["source"]] = by_source.get(row["source"], 0) + count
        by_priority[priority_names[int(row["priority"])]] += count
    return {"total": total, "by_source": by_source, "by_priority": by_priority}


def _missing_selection(
    date_from: str,
    *,
    scope: str,
    source: str,
    date_to: str | None,
    as_of: str | None,
    retry_failures_after_hours: float,
) -> tuple[str, str, list[Any]]:
    reference_date = as_of or date.today().isoformat()
    reference_start = f"{reference_date}T00:00:00"
    reference_end = f"{reference_date}T23:59:59"
    retry_cutoff = (
        datetime.now().astimezone() - timedelta(hours=retry_failures_after_hours)
    ).isoformat()
    range_end = date_to or reference_date
    range_start = f"{date_from}T00:00:00"
    range_end_exclusive = (
        date.fromisoformat(range_end) + timedelta(days=1)
    ).isoformat() + "T00:00:00"
    if scope == "publication":
        scope_condition = "o.published_at >= ? AND o.published_at < ?"
        scope_params: list[Any] = [range_start, range_end_exclusive]
    elif scope == "opening":
        scope_condition = "o.proposal_start_at >= ? AND o.proposal_start_at < ?"
        scope_params = [range_start, range_end_exclusive]
    elif scope == "closing":
        scope_condition = "o.proposal_end_at >= ? AND o.proposal_end_at < ?"
        scope_params = [range_start, range_end_exclusive]
    else:
        scope_condition = """(
            COALESCE(o.proposal_end_at, '') >= ?
            OR COALESCE(o.proposal_start_at, '') >= ?
        )"""
        scope_params = [reference_start, reference_start]
    source_condition = "1 = 1" if source == "all" else "o.source = ?"
    source_params: list[Any] = [] if source == "all" else [source]
    priority_sql = """CASE
        WHEN COALESCE(o.proposal_end_at, '') >= ?
         AND (COALESCE(o.proposal_start_at, '') = '' OR o.proposal_start_at <= ?)
          THEN 0
        WHEN COALESCE(o.proposal_start_at, '') > ? THEN 1
        WHEN COALESCE(o.proposal_end_at, '') >= ? THEN 2
        ELSE 3
    END"""
    where_sql = f"""{scope_condition}
          AND {source_condition}
          AND o.source_cnpj IS NOT NULL
          AND o.year IS NOT NULL
          AND o.sequence IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM opportunity_items i WHERE i.opportunity_id = o.id
          )
          AND NOT EXISTS (
              SELECT 1
              FROM source_records failed
              WHERE failed.source = 'pncp'
                AND failed.external_key = o.external_key
                AND failed.source_endpoint = 'item_enrichment_batch'
                AND failed.status = 'failed'
                AND failed.captured_at >= ?
          )
    """
    params: list[Any] = [
        reference_start,
        reference_end,
        reference_end,
        reference_start,
        *scope_params,
        *source_params,
        retry_cutoff,
    ]
    return priority_sql, where_sql, params


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
    if repository.opportunity_has_items(row["id"]):
        return "skipped", 0, 0, ["items already indexed by another worker"]

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
