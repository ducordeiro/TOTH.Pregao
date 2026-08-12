"""Persistent PNCP publication backfill runner for high-priority dates.

Runs each date/modality as an isolated unit so a single rate-limit response does
not end the whole queue.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.connectors import HttpJsonClient, PNCPConnector
from etl.jobs import run_backfill


DEFAULT_DATABASE = PROJECT_ROOT / "data" / "pncp.sqlite3"
DEFAULT_MODALITIES = tuple(range(1, 15))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--modality-code", type=int, action="append")
    parser.add_argument("--cycles", type=int, default=0, help="0 means keep running")
    parser.add_argument("--unit-delay", type=float, default=20.0)
    parser.add_argument("--cycle-delay", type=float, default=300.0)
    parser.add_argument("--rate-limit-backoff", type=float, default=180.0)
    parser.add_argument("--endpoint-cooldown", type=float, default=300.0)
    parser.add_argument("--unit-retries", type=int, default=1)
    parser.add_argument("--request-delay", type=float, default=3.0)
    parser.add_argument("--fallback-open-on-rate-limit", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)
    modalities = args.modality_code or list(DEFAULT_MODALITIES)
    cycle = 0
    connector = PNCPConnector(
        client=HttpJsonClient(
            timeout=60,
            retries=2,
            request_delay=args.request_delay,
        )
    )

    while args.cycles == 0 or cycle < args.cycles:
        cycle += 1
        cycle_summary: dict[str, Any] = {
            "cycle": cycle,
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "fetched": 0,
            "inserted": 0,
            "updated": 0,
            "fallback_completed": 0,
            "fallback_failed": 0,
            "errors": [],
        }
        for day in _date_range(start, end):
            day_text = day.isoformat()
            for modality in modalities:
                result = run_backfill(
                    args.database,
                    date_from=day_text,
                    date_to=day_text,
                    modality_codes=[modality],
                    resume=True,
                    unit_retries=args.unit_retries,
                    delay=0,
                    retry_backoff=args.unit_delay,
                    rate_limit_backoff=args.rate_limit_backoff,
                    endpoint_cooldown=args.endpoint_cooldown,
                    window_days=1,
                    defer_retries=True,
                    fallback_open_on_rate_limit=args.fallback_open_on_rate_limit,
                    connector=connector,
                )
                _merge(cycle_summary, result)
                print(json.dumps({
                    "unit": {"date": day_text, "modality": modality},
                    "result": result,
                }, ensure_ascii=False), flush=True)
                time.sleep(args.unit_delay)
        print(json.dumps({"cycle_summary": cycle_summary}, ensure_ascii=False), flush=True)
        if args.cycles == 0 or cycle < args.cycles:
            time.sleep(args.cycle_delay)
    return 0


def _date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in (
        "completed",
        "failed",
        "skipped",
        "fetched",
        "inserted",
        "updated",
        "fallback_completed",
        "fallback_failed",
    ):
        target[key] += int(source.get(key, 0))
    target["errors"].extend(source.get("errors", []))


if __name__ == "__main__":
    raise SystemExit(main())
