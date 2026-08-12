"""Refresh PNCP opportunities that are still receiving proposals."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.connectors import HttpJsonClient, PNCPConnector
from etl.jobs import DEFAULT_DATABASE, run_open_proposals


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh open PNCP proposal opportunities")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-final", default=(date.today() + timedelta(days=30)).isoformat())
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retry-backoff", type=float, default=15.0)
    parser.add_argument("--request-delay", type=float, default=4.0)
    parser.add_argument("--page-size", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--max-records", type=int, default=5000)
    details_group = parser.add_mutually_exclusive_group()
    details_group.add_argument("--fetch-details", dest="fetch_details", action="store_true", default=True)
    details_group.add_argument("--no-details", dest="fetch_details", action="store_false")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--cycle-delay", type=float, default=300.0)
    args = parser.parse_args()

    failures = 0
    for cycle in range(1, args.cycles + 1):
        client = HttpJsonClient(
            timeout=args.timeout,
            retries=args.retries,
            retry_backoff=args.retry_backoff,
            request_delay=args.request_delay,
        )
        connector = PNCPConnector(client=client, page_size=args.page_size)
        try:
            result = run_open_proposals(
                args.database,
                end_date=args.date_final,
                max_pages=args.max_pages,
                max_records=args.max_records,
                fetch_details=args.fetch_details,
                connector=connector,
            )
            print(json.dumps({"cycle": cycle, "result": result}, ensure_ascii=False), flush=True)
        except Exception as exc:
            failures += 1
            print(json.dumps({"cycle": cycle, "status": "failed", "error": str(exc)}, ensure_ascii=False), flush=True)
        if cycle < args.cycles:
            time.sleep(args.cycle_delay)
    return 1 if failures == args.cycles else 0


if __name__ == "__main__":
    raise SystemExit(main())
