"""Sweep PNCP open proposal pages independently so failures do not block progress."""

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
    parser = argparse.ArgumentParser(description="Fast PNCP open proposal page sweep")
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--date-final", default=(date.today() + timedelta(days=30)).isoformat())
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--end-page", type=int, default=500)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--retry-backoff", type=float, default=5.0)
    parser.add_argument("--request-delay", type=float, default=0.8)
    parser.add_argument("--page-delay", type=float, default=0.2)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--cycle-delay", type=float, default=60.0)
    args = parser.parse_args()

    failures = 0
    successes = 0
    for cycle in range(1, args.cycles + 1):
        for page in range(args.start_page, args.end_page + 1):
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
                    filters={"pagina": page},
                    max_pages=1,
                    max_records=args.page_size,
                    fetch_details=False,
                    connector=connector,
                )
                successes += 1
                print(
                    json.dumps(
                        {"cycle": cycle, "page": page, "status": "success", "result": result},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            except Exception as exc:
                failures += 1
                print(
                    json.dumps(
                        {"cycle": cycle, "page": page, "status": "failed", "error": str(exc)},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if args.page_delay:
                time.sleep(args.page_delay)
        if cycle < args.cycles:
            time.sleep(args.cycle_delay)
    return 0 if successes else 1


if __name__ == "__main__":
    raise SystemExit(main())
