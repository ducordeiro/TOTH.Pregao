"""Fill stored opportunity items from the paginated Compras.gov bulk feed."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.connectors import ComprasGovConnector, HttpJsonClient
from etl.mappers import ComprasGovMapper
from etl.repository import ETLRepository


DEFAULT_DATABASE = PROJECT_ROOT / "data" / "pncp.sqlite3"
DEFAULT_DATE_FROM = "2026-06-01"
DEFAULT_ENDPOINT = "/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133"
DEFAULT_STATUS_FILE = PROJECT_ROOT / "data" / "comprasgov_items_bulk.status.json"
DEFAULT_PID_FILE = PROJECT_ROOT / "data" / "comprasgov_items_bulk.pid"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-from", default=DEFAULT_DATE_FROM)
    parser.add_argument("--date-to", default=date.today().isoformat())
    parser.add_argument(
        "--stored-source",
        choices=("all", "pncp", "comprasgov"),
        default="comprasgov",
        help="Stored opportunity source to enrich from the Compras.gov item feed.",
    )
    parser.add_argument("--base-url", default="https://dadosabertos.compras.gov.br")
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=2.0)
    parser.add_argument("--request-delay", type=float, default=0.25)
    parser.add_argument("--status-file", default=str(DEFAULT_STATUS_FILE))
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        date_from = date.fromisoformat(args.date_from)
        date_to = date.fromisoformat(args.date_to)
    except ValueError as exc:
        raise SystemExit("dates must use YYYY-MM-DD") from exc
    if date_from > date_to:
        raise SystemExit("--date-from must be earlier than or equal to --date-to")
    if not 10 <= args.page_size <= 500:
        raise SystemExit("--page-size must be between 10 and 500")
    if args.timeout <= 0 or args.retries < 0 or args.request_delay < 0:
        raise SystemExit("timeout must be positive; retries and delay cannot be negative")

    repository = ETLRepository(args.database)
    repository.initialize()
    status_path = Path(args.status_file) if args.status_file else None
    pid_path = Path(args.pid_file) if args.pid_file else None
    if pid_path is not None:
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="utf-8")

    previous = None if args.restart else _read_status(status_path)
    pending_dates, failed_dates = _pending_dates(
        date_from,
        date_to,
        previous,
        stored_source=args.stored_source,
    )
    control_map = _load_control_map(repository, args.stored_source)
    connector = ComprasGovConnector(
        base_url=args.base_url,
        resource_path=args.endpoint,
        page_size=args.page_size,
        client=HttpJsonClient(
            timeout=args.timeout,
            retries=args.retries,
            retry_backoff=args.retry_backoff,
            request_delay=args.request_delay,
        ),
    )
    mapper = ComprasGovMapper()
    run_id = repository.create_run(
        "comprasgov",
        "bulk_item_enrichment",
        {
            "date_from": args.date_from,
            "date_to": args.date_to,
            "stored_source": args.stored_source,
            "endpoint": args.endpoint,
            "page_size": args.page_size,
            "dry_run": args.dry_run,
        },
    )
    counters = {
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
        "pages": 0,
        "matched_records": 0,
        "unmatched_records": 0,
        "items": 0,
    }
    started_at = datetime.now().astimezone()
    next_date = pending_dates[0].isoformat() if pending_dates else (date_to + timedelta(days=1)).isoformat()

    try:
        _write_status(
            status_path,
            _status_payload(
                run_id,
                args,
                counters,
                date_from,
                date_to,
                started_at,
                "running",
                next_date=next_date,
                failed_dates=failed_dates,
            ),
        )
        for current_date in pending_dates:
            current_text = current_date.isoformat()
            selected: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
            day_fetched = 0
            day_matched = 0
            day_unmatched = 0
            day_pages = 0
            current_total_pages = None
            request_url = args.endpoint
            try:
                for page in connector.iter_endpoint(
                    args.endpoint,
                    {
                        "dataInclusaoPncpInicial": current_text,
                        # Compras.gov treats the upper date bound as exclusive.
                        "dataInclusaoPncpFinal": (
                            current_date + timedelta(days=1)
                        ).isoformat(),
                    },
                ):
                    day_pages += 1
                    current_total_pages = page.total_pages
                    request_url = page.request_url
                    fetched, matched, unmatched = _collect_page(
                        selected,
                        page.records,
                        control_map,
                    )
                    day_fetched += fetched
                    day_matched += matched
                    day_unmatched += unmatched
                    _write_status(
                        status_path,
                        _status_payload(
                            run_id,
                            args,
                            counters,
                            date_from,
                            date_to,
                            started_at,
                            "running",
                            next_date=current_text,
                            failed_dates=failed_dates,
                            current_date=current_text,
                            current_page=day_pages,
                            current_total_pages=current_total_pages,
                            current_records=day_fetched,
                        ),
                    )
            except Exception as exc:
                counters["failed"] += 1
                if current_text not in failed_dates:
                    failed_dates.append(current_text)
                repository.save_failed_source_record(
                    run_id=run_id,
                    source="comprasgov",
                    source_endpoint="bulk_item_enrichment",
                    request_url=request_url,
                    raw_payload={
                        "date": current_text,
                        "pages_received": day_pages,
                        "records_received": day_fetched,
                    },
                    error_message=str(exc),
                    external_key=current_text,
                )
                print(
                    json.dumps({"date": current_text, "error": str(exc)}, ensure_ascii=False),
                    flush=True,
                )
                continue

            batches = {
                opportunity_id: mapper.map_items(
                    sorted(records.values(), key=_item_sort_key)
                )
                for opportunity_id, records in selected.items()
            }
            persistence = (
                {"opportunities": len(batches), "items": sum(map(len, batches.values()))}
                if args.dry_run
                else repository.merge_opportunity_items(batches)
            )
            counters["fetched"] += day_fetched
            counters["updated"] += persistence["opportunities"]
            counters["skipped"] += day_unmatched
            counters["pages"] += day_pages
            counters["matched_records"] += day_matched
            counters["unmatched_records"] += day_unmatched
            counters["items"] += persistence["items"]
            failed_dates = [value for value in failed_dates if value != current_text]
            next_date = (current_date + timedelta(days=1)).isoformat()
            repository.update_run_progress(run_id, counters)
            _write_status(
                status_path,
                _status_payload(
                    run_id,
                    args,
                    counters,
                    date_from,
                    date_to,
                    started_at,
                    "running",
                    next_date=next_date,
                    failed_dates=failed_dates,
                ),
            )
            print(
                json.dumps(
                    {
                        "date": current_text,
                        "pages": day_pages,
                        "fetched": day_fetched,
                        "matched": day_matched,
                        "unmatched": day_unmatched,
                        **persistence,
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    except Exception as exc:
        repository.finish_run(
            run_id,
            status="failed",
            counters=counters,
            error_message=str(exc),
        )
        _write_status(
            status_path,
            _status_payload(
                run_id,
                args,
                counters,
                date_from,
                date_to,
                started_at,
                "failed",
                next_date=next_date,
                failed_dates=failed_dates,
                error=str(exc),
            ),
        )
        raise
    finally:
        if pid_path is not None and pid_path.exists():
            try:
                if pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                    pid_path.unlink()
            except OSError:
                pass

    status = "dry_run" if args.dry_run else ("partial" if failed_dates else "success")
    repository.finish_run(run_id, status=status, counters=counters)
    _write_status(
        status_path,
        _status_payload(
            run_id,
            args,
            counters,
            date_from,
            date_to,
            started_at,
            status,
            next_date=next_date,
            failed_dates=failed_dates,
        ),
    )
    print(json.dumps({"run_id": run_id, "status": status, **counters}, indent=2))
    return 0 if not failed_dates else 2


def _load_control_map(repository: ETLRepository, stored_source: str) -> dict[str, str]:
    where = "" if stored_source == "all" else "WHERE source = ?"
    params: tuple[Any, ...] = () if stored_source == "all" else (stored_source,)
    with repository.connect() as connection:
        rows = connection.execute(
            f"""
            SELECT id, external_key, pncp_control_number
            FROM opportunities
            {where}
            """,
            params,
        ).fetchall()
    mapping: dict[str, str] = {}
    for row in rows:
        for value in (row["external_key"], row["pncp_control_number"]):
            key = _text(value)
            if key:
                mapping[key] = row["id"]
    return mapping


def _collect_page(
    selected: dict[str, dict[tuple[str, str], dict[str, Any]]],
    records: list[dict[str, Any]],
    control_map: dict[str, str],
) -> tuple[int, int, int]:
    matched = 0
    unmatched = 0
    for record in records:
        control = _text(
            record.get("numeroControlePNCPCompra")
            or record.get("idContratacaoPNCP")
        )
        opportunity_id = control_map.get(control)
        if not opportunity_id:
            unmatched += 1
            continue
        matched += 1
        identity = _item_identity(record)
        current = selected.setdefault(opportunity_id, {}).get(identity)
        if current is None or _record_rank(record) >= _record_rank(current):
            selected[opportunity_id][identity] = record
    return len(records), matched, unmatched


def _item_identity(record: dict[str, Any]) -> tuple[str, str]:
    group = _text(record.get("numeroGrupo"))
    if group in {"0", "0.0"}:
        group = ""
    number = _text(
        record.get("numeroItemPncp")
        or record.get("numeroItemCompra")
        or record.get("idCompraItem")
    )
    return group, number


def _record_rank(record: dict[str, Any]) -> tuple[str, int, int]:
    status = _text(record.get("situacaoCompraItemNome")).casefold()
    status_rank = {
        "homologado": 4,
        "adjudicado": 3,
        "fracassado": 2,
        "deserto": 2,
        "revogado": 2,
        "anulado": 2,
        "em andamento": 1,
    }.get(status, 0)
    return (
        _text(record.get("dataAtualizacaoPncp")),
        int(bool(record.get("temResultado"))),
        status_rank,
    )


def _item_sort_key(record: dict[str, Any]) -> tuple[int, str, int, str]:
    group, number = _item_identity(record)
    return (*_numeric_text_key(group), *_numeric_text_key(number))


def _numeric_text_key(value: str) -> tuple[int, str]:
    try:
        return int(value or 0), value
    except ValueError:
        return sys.maxsize, value


def _pending_dates(
    date_from: date,
    date_to: date,
    previous: dict[str, Any] | None,
    *,
    stored_source: str,
) -> tuple[list[date], list[str]]:
    next_date = date_from
    failed_dates: list[str] = []
    if (
        previous
        and previous.get("date_from") == date_from.isoformat()
        and previous.get("date_to") == date_to.isoformat()
        and previous.get("stored_source") == stored_source
    ):
        try:
            next_date = max(date_from, date.fromisoformat(previous.get("next_date", "")))
        except ValueError:
            next_date = date_from
        failed_dates = [
            value
            for value in previous.get("failed_dates", [])
            if date_from.isoformat() <= value <= date_to.isoformat()
        ]
    dates = {
        date.fromisoformat(value)
        for value in failed_dates
    }
    current = next_date
    while current <= date_to:
        dates.add(current)
        current += timedelta(days=1)
    return sorted(dates), failed_dates


def _status_payload(
    run_id: str,
    args: argparse.Namespace,
    counters: dict[str, int],
    date_from: date,
    date_to: date,
    started_at: datetime,
    status: str,
    *,
    next_date: str,
    failed_dates: list[str],
    current_date: str | None = None,
    current_page: int = 0,
    current_total_pages: int | None = None,
    current_records: int = 0,
    error: str = "",
) -> dict[str, Any]:
    now = datetime.now().astimezone()
    total_days = (date_to - date_from).days + 1
    try:
        completed_days = min(max((date.fromisoformat(next_date) - date_from).days, 0), total_days)
    except ValueError:
        completed_days = 0
    elapsed = max((now - started_at).total_seconds(), 0.001)
    days_per_second = completed_days / elapsed
    remaining_days = max(total_days - completed_days, 0)
    return {
        "run_id": run_id,
        "pid": os.getpid(),
        "status": status,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "stored_source": args.stored_source,
        "next_date": next_date,
        "failed_dates": sorted(set(failed_dates)),
        "total_days": total_days,
        "completed_days": completed_days,
        "progress_percent": round(completed_days / total_days * 100, 2),
        "estimated_seconds_remaining": (
            round(remaining_days / days_per_second) if days_per_second else None
        ),
        "current_date": current_date,
        "current_page": current_page,
        "current_total_pages": current_total_pages,
        "current_records": current_records,
        "counters": dict(counters),
        "started_at": started_at.isoformat(),
        "updated_at": now.isoformat(),
        "error": error,
    }


def _read_status(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


if __name__ == "__main__":
    raise SystemExit(main())
