"""Start the resumable hybrid backfill as a detached Windows process."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    data = root / "data"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdout_path = data / f"hybrid_backfill_resume_{stamp}.out.log"
    stderr_path = data / f"hybrid_backfill_resume_{stamp}.err.log"
    command = [
        sys.executable,
        "-m",
        "etl",
        "--timeout",
        "45",
        "--retries",
        "2",
        "hybrid-backfill",
        "--date-from",
        "2026-04-01",
        "--date-to",
        "2026-08-06",
        "--window-days",
        "7",
        "--request-delay",
        "1.5",
        "--delay",
        "0.5",
        "--unit-retries",
        "24",
        "--bulk-retries",
        "8",
    ]
    flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        process = subprocess.Popen(
            command,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=stdout,
            stderr=stderr,
            creationflags=flags,
            close_fds=True,
        )
    status = {
        "pid": process.pid,
        "started": datetime.now().astimezone().isoformat(),
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
        "mode": "hybrid-comprasgov-pncp-resume",
        "date_from": "2026-04-01",
        "date_to": "2026-08-06",
        "window_days": 7,
        "request_delay": 1.5,
    }
    (data / "backfill.pid").write_text(str(process.pid), encoding="ascii")
    (data / "backfill.status").write_text(
        "".join(f"{key}={value}\n" for key, value in status.items()), encoding="utf-8-sig"
    )
    print(json.dumps(status, ensure_ascii=False))


if __name__ == "__main__":
    main()
