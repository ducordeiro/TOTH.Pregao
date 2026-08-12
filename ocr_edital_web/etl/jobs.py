"""Runnable ETL jobs and a small stdlib-only command-line interface."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Sequence

from .classifier import OpportunityClassifier
from .connectors import ComprasGovConnector, HttpJsonClient, PNCPConnector
from .mappers import ComprasGovMapper, PNCPMapper
from .repository import ETLRepository
from .service import ETLSyncService, SyncRequest


DEFAULT_MODALITY_CODES = tuple(range(1, 20))
DEFAULT_DATABASE = Path(__file__).resolve().parent.parent / "data" / "pncp.sqlite3"
DETAILS_REQUIRED_FROM = date(2026, 7, 1)


def run_backfill(
    database_path: str | Path,
    *,
    date_from: str | date,
    date_to: str | date,
    modality_codes: Sequence[int] = DEFAULT_MODALITY_CODES,
    dry_run: bool = False,
    max_pages: int | None = None,
    max_records: int | None = None,
    fetch_details: bool = True,
    resume: bool = True,
    unit_retries: int = 2,
    delay: float = 1.0,
    retry_backoff: float = 5.0,
    rate_limit_backoff: float = 30.0,
    window_days: int = 1,
    defer_retries: bool = False,
    fallback_open_on_rate_limit: bool = False,
    endpoint_cooldown: float | None = None,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
    sleeper: Any = time.sleep,
) -> dict[str, Any]:
    """Backfill PNCP publications using resumable date-window/modality units."""
    start = date.fromisoformat(_iso_date(date_from))
    end = date.fromisoformat(_iso_date(date_to))
    if start > end:
        raise ValueError("date_from must be earlier than or equal to date_to")
    modalities = tuple(dict.fromkeys(int(value) for value in modality_codes))
    if not modalities or any(value < 1 or value > 19 for value in modalities):
        raise ValueError("modality_codes must contain values from 1 to 19")
    if unit_retries < 0:
        raise ValueError("unit_retries must be zero or greater")
    if window_days < 1 or window_days > 30:
        raise ValueError("window_days must be between 1 and 30")
    if delay < 0 or retry_backoff < 0 or rate_limit_backoff < 0:
        raise ValueError("delay and backoff values must be zero or greater")
    cooldown_seconds = rate_limit_backoff if endpoint_cooldown is None else endpoint_cooldown
    if cooldown_seconds < 0:
        raise ValueError("endpoint_cooldown must be zero or greater")

    repository = ETLRepository(database_path)
    repository.initialize()
    service = ETLSyncService(
        repository,
        connector or PNCPConnector(),
        PNCPMapper(),
        OpportunityClassifier(),
    )
    summary: dict[str, Any] = {
        "status": "success",
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "modalities": list(modalities),
        "window_days": window_days,
        "details_required_from": DETAILS_REQUIRED_FROM.isoformat(),
        "completed": 0,
        "skipped": 0,
        "failed": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "fallback_completed": 0,
        "fallback_failed": 0,
        "endpoint_cooldowns": 0,
        "errors": [],
    }

    units = [
        (window_start, window_end, modality)
        for window_start, window_end in _date_windows(start, end, window_days)
        for modality in modalities
    ]
    deferred_attempts: dict[tuple[date, date, int], int] = {}
    publicacao_cooldown_until = 0.0
    for unit_index, (window_start, window_end, modality) in enumerate(units):
        unit_key = (window_start, window_end, modality)
        start_text = window_start.isoformat()
        end_text = window_end.isoformat()
        unit_fetch_details = fetch_details or _details_required_for_window(window_start, window_end)
        attempted = False
        now = time.monotonic()
        if publicacao_cooldown_until > now:
            if fallback_open_on_rate_limit:
                if _run_open_proposals_fallback(
                    service,
                    end_text=end_text,
                    modality=modality,
                    max_pages=max_pages,
                    max_records=max_records,
                    fetch_details=unit_fetch_details,
                    dry_run=dry_run,
                    company_profile=company_profile or {},
                    summary=summary,
                ):
                    summary["fallback_completed"] += 1
                else:
                    summary["fallback_failed"] += 1
            units.append(unit_key)
            remaining = publicacao_cooldown_until - now
            if delay:
                sleeper(min(delay, remaining))
            continue
        checkpoint_enabled = (
            resume and not dry_run and max_pages is None and max_records is None
        )
        checkpoint = repository.get_backfill_checkpoint(
            source="pncp",
            endpoint="publicacao",
            date_from=start_text,
            date_to=end_text,
            modality_code=modality,
        ) if checkpoint_enabled else None
        if checkpoint_enabled and repository.has_covering_backfill_checkpoint(
            source="pncp",
            endpoint="publicacao",
            date_from=start_text,
            date_to=end_text,
            modality_code=modality,
        ):
            summary["skipped"] += 1
            continue
        if checkpoint and checkpoint["completed"]:
            summary["skipped"] += 1
            continue

        legacy_completed = resume and repository.has_completed_checkpoint(
            source="pncp",
            run_type="backfill",
            target_date=start_text,
            target_end_date=end_text,
            modality_code=modality,
            dry_run=dry_run,
            max_pages=max_pages,
            max_records=max_records,
            fetch_details=unit_fetch_details,
        )
        if legacy_completed:
            if checkpoint_enabled:
                repository.save_backfill_checkpoint(
                    source="pncp",
                    endpoint="publicacao",
                    date_from=start_text,
                    date_to=end_text,
                    modality_code=modality,
                    next_page=int((checkpoint or {}).get("next_page", 1)),
                    completed=True,
                )
            summary["skipped"] += 1
            continue

        next_page = int((checkpoint or {}).get("next_page", 1))
        if checkpoint_enabled and checkpoint is None:
            next_page = repository.recover_backfill_next_page(
                source="pncp",
                run_type="backfill",
                date_from=start_text,
                date_to=end_text,
                modality_code=modality,
            )
            repository.save_backfill_checkpoint(
                source="pncp",
                endpoint="publicacao",
                date_from=start_text,
                date_to=end_text,
                modality_code=modality,
                next_page=next_page,
            )

        last_error: Exception | None = None
        first_attempt = deferred_attempts.get(unit_key, 0)
        attempt_range = (
            range(first_attempt, min(first_attempt + 1, unit_retries + 1))
            if defer_retries
            else range(unit_retries + 1)
        )
        for attempt in attempt_range:
            attempted = True
            try:
                def page_completed(page):
                    if checkpoint_enabled:
                        repository.save_backfill_checkpoint(
                            source="pncp",
                            endpoint="publicacao",
                            date_from=start_text,
                            date_to=end_text,
                            modality_code=modality,
                            next_page=page.page_number + 1,
                        )

                result = service.sync(SyncRequest(
                    endpoint="publicacao",
                    filters={
                        "date_from": start_text,
                        "date_to": end_text,
                        "modality_codes": [modality],
                        "pagina": next_page,
                    },
                    run_type="backfill",
                    dry_run=dry_run,
                    max_pages=max_pages,
                    max_records=max_records,
                    fetch_details=unit_fetch_details,
                    company_profile=company_profile or {},
                    page_completed=page_completed,
                ))
                if checkpoint_enabled:
                    latest_checkpoint = repository.get_backfill_checkpoint(
                        source="pncp",
                        endpoint="publicacao",
                        date_from=start_text,
                        date_to=end_text,
                        modality_code=modality,
                    ) or {"next_page": next_page}
                    repository.save_backfill_checkpoint(
                        source="pncp",
                        endpoint="publicacao",
                        date_from=start_text,
                        date_to=end_text,
                        modality_code=modality,
                        next_page=int(latest_checkpoint["next_page"]),
                        completed=True,
                    )
                summary["completed"] += 1
                summary["fetched"] += int(result.get("fetched", 0))
                summary["inserted"] += int(result.get("inserted", 0))
                summary["updated"] += int(result.get("updated", 0))
                summary["unchanged"] += int(result.get("skipped", 0))
                deferred_attempts.pop(unit_key, None)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if attempt < unit_retries:
                    if checkpoint_enabled:
                        checkpoint = repository.get_backfill_checkpoint(
                            source="pncp",
                            endpoint="publicacao",
                            date_from=start_text,
                            date_to=end_text,
                            modality_code=modality,
                        )
                        next_page = int((checkpoint or {}).get("next_page", next_page))
                    is_rate_limited = _is_rate_limit_error(exc)
                    base = rate_limit_backoff if is_rate_limited else retry_backoff
                    if is_rate_limited:
                        summary["endpoint_cooldowns"] += 1
                        publicacao_cooldown_until = max(
                            publicacao_cooldown_until,
                            time.monotonic() + cooldown_seconds,
                        )
                        if fallback_open_on_rate_limit:
                            if _run_open_proposals_fallback(
                                service,
                                end_text=end_text,
                                modality=modality,
                                max_pages=max_pages,
                                max_records=max_records,
                                fetch_details=unit_fetch_details,
                                dry_run=dry_run,
                                company_profile=company_profile or {},
                                summary=summary,
                            ):
                                summary["fallback_completed"] += 1
                            else:
                                summary["fallback_failed"] += 1
                    if defer_retries:
                        deferred_attempts[unit_key] = attempt + 1
                        units.append(unit_key)
                        if is_rate_limited:
                            sleeper(min(base * (2 ** min(attempt, 8)), 900.0))
                        last_error = None
                        break
                    sleeper(min(base * (2 ** min(attempt, 8)), 900.0))
        if last_error is not None:
            summary["failed"] += 1
            summary["errors"].append({
                "date_from": start_text,
                "date_to": end_text,
                "modality": modality,
                "error": str(last_error),
            })
        if attempted and delay and unit_index < len(units) - 1:
            sleeper(delay)

    if summary["failed"]:
        summary["status"] = "partial"
    elif dry_run:
        summary["status"] = "dry_run"
    return summary


def run_daily(
    database_path: str | Path,
    *,
    target_date: str | date | None = None,
    modality_codes: Sequence[int] = DEFAULT_MODALITY_CODES,
    dry_run: bool = False,
    max_pages: int | None = 10,
    max_records: int | None = 1000,
    fetch_details: bool = True,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
) -> dict[str, Any]:
    day = _iso_date(target_date or date.today())
    return _pncp_service(database_path, connector).sync(
        SyncRequest(
            endpoint="publicacao",
            filters={"date_from": day, "date_to": day, "modality_codes": list(modality_codes)},
            run_type="daily",
            dry_run=dry_run,
            max_pages=max_pages,
            max_records=max_records,
            fetch_details=fetch_details,
            company_profile=company_profile or {},
        )
    )


def run_updates(
    database_path: str | Path,
    *,
    date_from: str | date,
    date_to: str | date | None = None,
    modality_codes: Sequence[int] = DEFAULT_MODALITY_CODES,
    dry_run: bool = False,
    max_pages: int | None = 10,
    max_records: int | None = 1000,
    fetch_details: bool = True,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
) -> dict[str, Any]:
    return _pncp_service(database_path, connector).sync(
        SyncRequest(
            endpoint="atualizacao",
            filters={
                "date_from": _iso_date(date_from),
                "date_to": _iso_date(date_to or date.today()),
                "modality_codes": list(modality_codes),
            },
            run_type="update",
            dry_run=dry_run,
            max_pages=max_pages,
            max_records=max_records,
            fetch_details=fetch_details,
            company_profile=company_profile or {},
        )
    )


def run_open_proposals(
    database_path: str | Path,
    *,
    end_date: str | date | None = None,
    filters: dict[str, Any] | None = None,
    dry_run: bool = False,
    max_pages: int | None = 10,
    max_records: int | None = 1000,
    fetch_details: bool = True,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
) -> dict[str, Any]:
    query = dict(filters or {})
    query["dataFinal"] = _iso_date(end_date or date.today())
    return _pncp_service(database_path, connector).sync(
        SyncRequest(
            endpoint="proposta",
            filters=query,
            run_type="open_proposals",
            dry_run=dry_run,
            max_pages=max_pages,
            max_records=max_records,
            fetch_details=fetch_details,
            company_profile=company_profile or {},
        )
    )


def run_comprasgov(
    database_path: str | Path,
    *,
    filters: dict[str, Any] | None = None,
    resource_path: str | None = None,
    dry_run: bool = False,
    max_pages: int | None = 10,
    max_records: int | None = 1000,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
) -> dict[str, Any]:
    query = dict(filters or {})
    required_filters = (
        "dataPublicacaoPncpInicial",
        "dataPublicacaoPncpFinal",
        "codigoModalidade",
    )
    missing = [name for name in required_filters if query.get(name) in (None, "")]
    if missing:
        raise ValueError(
            "Compras.gov requires filters: " + ", ".join(missing)
        )
    connector = connector or ComprasGovConnector(
        base_url=os.environ.get("COMPRASGOV_BASE_URL", "https://dadosabertos.compras.gov.br"),
        resource_path=resource_path
        or os.environ.get(
            "COMPRASGOV_RESOURCE_PATH",
            "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
        ),
    )
    service = ETLSyncService(
        ETLRepository(database_path), connector, ComprasGovMapper(), OpportunityClassifier()
    )
    return service.sync(
        SyncRequest(
            endpoint=connector.resource_path,
            filters=query,
            run_type="complementary",
            dry_run=dry_run,
            max_pages=max_pages,
            max_records=max_records,
            fetch_details=False,
            company_profile=company_profile or {},
        )
    )


def run_comprasgov_backfill(
    database_path: str | Path,
    *,
    date_from: str | date,
    date_to: str | date,
    modality_codes: Sequence[int] = DEFAULT_MODALITY_CODES,
    unit_retries: int = 8,
    delay: float = 0.25,
    company_profile: dict[str, Any] | None = None,
    connector: Any | None = None,
    sleeper: Any = time.sleep,
) -> dict[str, Any]:
    """Seed opportunities from the faster Compras.gov feed using 500-row pages."""
    start_text = _iso_date(date_from)
    end_text = _iso_date(date_to)
    if start_text > end_text:
        raise ValueError("date_from must be earlier than or equal to date_to")
    modalities = tuple(dict.fromkeys(int(value) for value in modality_codes))
    if not modalities or any(value < 1 or value > 19 for value in modalities):
        raise ValueError("modality_codes must contain values from 1 to 19")
    if unit_retries < 0 or delay < 0:
        raise ValueError("unit_retries and delay must be zero or greater")

    repository = ETLRepository(database_path)
    repository.initialize()
    connector = connector or ComprasGovConnector(
        base_url=os.environ.get("COMPRASGOV_BASE_URL", "https://dadosabertos.compras.gov.br"),
        resource_path=os.environ.get(
            "COMPRASGOV_RESOURCE_PATH",
            "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
        ),
        page_size=500,
    )
    endpoint = getattr(connector, "resource_path", "/contratacoes")
    service = ETLSyncService(
        repository, connector, ComprasGovMapper(), OpportunityClassifier()
    )
    summary: dict[str, Any] = {
        "status": "success",
        "source": "comprasgov",
        "date_from": start_text,
        "date_to": end_text,
        "modalities": list(modalities),
        "completed": 0,
        "skipped": 0,
        "failed": 0,
        "fetched": 0,
        "inserted": 0,
        "updated": 0,
        "unchanged": 0,
        "errors": [],
    }
    queue = list(modalities)
    attempts = {modality: 0 for modality in modalities}

    for queue_index, modality in enumerate(queue):
        checkpoint = repository.get_backfill_checkpoint(
            source="comprasgov",
            endpoint=endpoint,
            date_from=start_text,
            date_to=end_text,
            modality_code=modality,
        )
        if checkpoint and checkpoint["completed"]:
            summary["skipped"] += 1
            continue
        next_page = int((checkpoint or {}).get("next_page", 1))

        def page_completed(page):
            repository.save_backfill_checkpoint(
                source="comprasgov",
                endpoint=endpoint,
                date_from=start_text,
                date_to=end_text,
                modality_code=modality,
                next_page=page.page_number + 1,
            )

        try:
            result = service.sync(SyncRequest(
                endpoint=endpoint,
                filters={
                    "dataPublicacaoPncpInicial": start_text,
                    "dataPublicacaoPncpFinal": end_text,
                    "codigoModalidade": modality,
                    "pagina": next_page,
                },
                run_type="comprasgov_backfill",
                max_pages=None,
                max_records=None,
                fetch_details=False,
                company_profile=company_profile or {},
                page_completed=page_completed,
            ))
            latest = repository.get_backfill_checkpoint(
                source="comprasgov",
                endpoint=endpoint,
                date_from=start_text,
                date_to=end_text,
                modality_code=modality,
            ) or {"next_page": next_page}
            repository.save_backfill_checkpoint(
                source="comprasgov",
                endpoint=endpoint,
                date_from=start_text,
                date_to=end_text,
                modality_code=modality,
                next_page=int(latest["next_page"]),
                completed=True,
            )
            summary["completed"] += 1
            summary["fetched"] += int(result.get("fetched", 0))
            summary["inserted"] += int(result.get("inserted", 0))
            summary["updated"] += int(result.get("updated", 0))
            summary["unchanged"] += int(result.get("skipped", 0))
        except Exception as exc:
            attempts[modality] += 1
            if attempts[modality] <= unit_retries:
                queue.append(modality)
            else:
                summary["failed"] += 1
                summary["errors"].append({
                    "modality": modality,
                    "error": str(exc),
                })
        if delay and queue_index < len(queue) - 1:
            sleeper(delay)

    if summary["failed"]:
        summary["status"] = "partial"
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TOTH opportunity ETL")
    parser.add_argument(
        "--database",
        default=os.environ.get("TOTH_DATABASE_PATH", str(DEFAULT_DATABASE)),
        help="SQLite database path",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retries", type=int, default=2)
    subparsers = parser.add_subparsers(dest="job", required=True)

    daily = subparsers.add_parser("daily", help="Import PNCP publications for one day")
    _add_common_options(daily)
    daily.add_argument("--date", default=date.today().isoformat())
    daily.add_argument("--modality-code", type=int, action="append")

    update = subparsers.add_parser("update", help="Import PNCP updates for a date range")
    _add_common_options(update)
    update.add_argument("--date-from", required=True)
    update.add_argument("--date-to", default=date.today().isoformat())
    update.add_argument("--modality-code", type=int, action="append")

    open_parser = subparsers.add_parser("open", help="Import opportunities receiving proposals")
    _add_common_options(open_parser)
    open_parser.add_argument("--date-final", default=date.today().isoformat())
    open_parser.add_argument("--filters-json", default="{}")

    compras = subparsers.add_parser("compras", help="Import the complementary Compras.gov feed")
    _add_common_options(compras, details=False)
    compras.add_argument("--resource-path")
    compras.add_argument("--filters-json", default="{}")

    hybrid = subparsers.add_parser(
        "hybrid-backfill",
        help="Seed from Compras.gov in 500-row pages, then complete nationally with PNCP",
    )
    _add_common_options(
        hybrid,
        details=False,
        default_max_pages=None,
        default_max_records=None,
    )
    hybrid.add_argument("--date-from", required=True)
    hybrid.add_argument("--date-to", required=True)
    hybrid.add_argument("--modality-code", type=int, action="append")
    hybrid.add_argument("--window-days", type=int, default=7)
    hybrid.add_argument("--request-delay", type=float, default=1.5)
    hybrid.add_argument("--delay", type=float, default=0.5)
    hybrid.add_argument("--unit-retries", type=int, default=24)
    hybrid.add_argument("--bulk-retries", type=int, default=8)
    hybrid.add_argument("--retry-backoff", type=float, default=3.0)
    hybrid.add_argument("--rate-limit-backoff", type=float, default=60.0)

    backfill = subparsers.add_parser(
        "backfill", help="Backfill PNCP publications by date window and modality"
    )
    _add_common_options(
        backfill,
        details=False,
        default_max_pages=None,
        default_max_records=None,
    )
    backfill.add_argument("--date-from", required=True)
    backfill.add_argument("--date-to", required=True)
    backfill.add_argument("--modality-code", type=int, action="append")
    details_group = backfill.add_mutually_exclusive_group()
    details_group.add_argument("--fetch-details", dest="fetch_details", action="store_true", default=True)
    details_group.add_argument("--no-details", dest="fetch_details", action="store_false")
    backfill.add_argument("--unit-retries", type=int, default=2)
    backfill.add_argument("--delay", type=float, default=1.0)
    backfill.add_argument("--retry-backoff", type=float, default=5.0)
    backfill.add_argument("--rate-limit-backoff", type=float, default=30.0)
    backfill.add_argument("--endpoint-cooldown", type=float)
    backfill.add_argument("--fallback-open-on-rate-limit", action="store_true")
    backfill.add_argument("--window-days", type=int, default=1)
    backfill.add_argument("--request-delay", type=float, default=0.0)
    backfill.add_argument("--defer-retries", action="store_true")
    resume_group = backfill.add_mutually_exclusive_group()
    resume_group.add_argument("--resume", dest="resume", action="store_true", default=True)
    resume_group.add_argument("--no-resume", dest="resume", action="store_false")

    args = parser.parse_args(argv)
    profile = _json_object(args.profile_json, "--profile-json")
    client = HttpJsonClient(
        timeout=args.timeout,
        retries=args.retries,
        request_delay=getattr(args, "request_delay", 0.0),
    )
    pncp = PNCPConnector(client=client)
    common = {
        "database_path": args.database,
        "dry_run": args.dry_run,
        "max_pages": args.max_pages,
        "max_records": args.max_records,
        "company_profile": profile,
    }
    if args.job == "hybrid-backfill":
        selected_modalities = args.modality_code or DEFAULT_MODALITY_CODES
        compras_result = run_comprasgov_backfill(
            args.database,
            date_from=args.date_from,
            date_to=args.date_to,
            modality_codes=selected_modalities,
            unit_retries=args.bulk_retries,
            delay=args.delay,
            company_profile=profile,
            connector=ComprasGovConnector(
                client=HttpJsonClient(timeout=args.timeout, retries=args.retries),
                page_size=500,
            ),
        )
        pncp_result = run_backfill(
            args.database,
            date_from=args.date_from,
            date_to=args.date_to,
            modality_codes=selected_modalities,
            max_pages=args.max_pages,
            max_records=args.max_records,
            fetch_details=True,
            company_profile=profile,
            resume=True,
            unit_retries=args.unit_retries,
            delay=args.delay,
            retry_backoff=args.retry_backoff,
            rate_limit_backoff=args.rate_limit_backoff,
            window_days=args.window_days,
            defer_retries=True,
            connector=pncp,
        )
        result = {"comprasgov": compras_result, "pncp": pncp_result}
    elif args.job == "backfill":
        result = run_backfill(
            date_from=args.date_from,
            date_to=args.date_to,
            modality_codes=args.modality_code or DEFAULT_MODALITY_CODES,
            fetch_details=args.fetch_details,
            resume=args.resume,
            unit_retries=args.unit_retries,
            delay=args.delay,
            retry_backoff=args.retry_backoff,
            rate_limit_backoff=args.rate_limit_backoff,
            endpoint_cooldown=args.endpoint_cooldown,
            fallback_open_on_rate_limit=args.fallback_open_on_rate_limit,
            window_days=args.window_days,
            defer_retries=args.defer_retries,
            connector=pncp,
            **common,
        )
    elif args.job == "daily":
        result = run_daily(
            target_date=args.date,
            modality_codes=args.modality_code or DEFAULT_MODALITY_CODES,
            fetch_details=not args.no_details,
            connector=pncp,
            **common,
        )
    elif args.job == "update":
        result = run_updates(
            date_from=args.date_from,
            date_to=args.date_to,
            modality_codes=args.modality_code or DEFAULT_MODALITY_CODES,
            fetch_details=not args.no_details,
            connector=pncp,
            **common,
        )
    elif args.job == "open":
        result = run_open_proposals(
            end_date=args.date_final,
            filters=_json_object(args.filters_json, "--filters-json"),
            fetch_details=not args.no_details,
            connector=pncp,
            **common,
        )
    else:
        result = run_comprasgov(
            resource_path=args.resource_path,
            filters=_json_object(args.filters_json, "--filters-json"),
            connector=ComprasGovConnector(client=client, resource_path=args.resource_path or os.environ.get(
                "COMPRASGOV_RESOURCE_PATH",
                "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
            )),
            **common,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _pncp_service(database_path: str | Path, connector: Any | None) -> ETLSyncService:
    return ETLSyncService(
        ETLRepository(database_path),
        connector or PNCPConnector(),
        PNCPMapper(),
        OpportunityClassifier(),
    )


def _run_open_proposals_fallback(
    service: ETLSyncService,
    *,
    end_text: str,
    modality: int,
    max_pages: int | None,
    max_records: int | None,
    fetch_details: bool,
    dry_run: bool,
    company_profile: dict[str, Any],
    summary: dict[str, Any],
) -> bool:
    proposal_end_text = max(end_text, date.today().isoformat())
    try:
        result = service.sync(
            SyncRequest(
                endpoint="proposta",
                filters={
                    "dataFinal": proposal_end_text,
                    "codigoModalidadeContratacao": modality,
                },
                run_type="fallback_open_proposals",
                dry_run=dry_run,
                max_pages=max_pages,
                max_records=max_records,
                fetch_details=fetch_details,
                company_profile=company_profile,
            )
        )
    except Exception as exc:
        summary["errors"].append({
            "endpoint": "proposta",
            "date_to": proposal_end_text,
            "publicacao_date_to": end_text,
            "modality": modality,
            "fallback": True,
            "error": str(exc),
        })
        return False
    summary["fetched"] += int(result.get("fetched", 0))
    summary["inserted"] += int(result.get("inserted", 0))
    summary["updated"] += int(result.get("updated", 0))
    summary["unchanged"] += int(result.get("skipped", 0))
    return True


def _add_common_options(
    parser: argparse.ArgumentParser,
    details: bool = True,
    *,
    default_max_pages: int | None = 10,
    default_max_records: int | None = 1000,
) -> None:
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-pages", type=int, default=default_max_pages)
    parser.add_argument("--max-records", type=int, default=default_max_records)
    parser.add_argument("--profile-json", default="{}")
    if details:
        parser.add_argument("--no-details", action="store_true")


def _json_object(value: str, name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{name} must contain valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SystemExit(f"{name} must contain a JSON object")
    return parsed


def _iso_date(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return date.fromisoformat(str(value)[:10]).isoformat()


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _date_windows(start: date, end: date, window_days: int):
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=window_days - 1), end)
        yield current, window_end
        current = window_end + timedelta(days=1)


def _details_required_for_window(window_start: date, window_end: date) -> bool:
    return window_end >= DETAILS_REQUIRED_FROM


def _is_rate_limit_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        message = str(current).casefold()
        if "429" in message or "limite de requisi" in message or "too many requests" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


if __name__ == "__main__":
    raise SystemExit(main())
