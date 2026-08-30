"""Create a compact, consistent SQLite copy suitable for sharing the app data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--name", default="pncp_operacional")
    args = parser.parse_args()

    source = args.source.resolve()
    output_directory = args.output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    database = output_directory / f"{args.name}.sqlite3"
    archive = output_directory / f"{args.name}.zip"
    checksum = output_directory / f"{args.name}.sha256"

    for target in (database, archive, checksum):
        if target.exists():
            raise SystemExit(f"Output already exists: {target}")

    started = time.monotonic()
    print(f"Creating consistent snapshot: {database}", flush=True)
    with sqlite3.connect(source, timeout=60) as source_connection:
        with sqlite3.connect(database, timeout=60) as target_connection:
            source_connection.backup(target_connection, pages=8192, sleep=0.05)

    print("Removing raw ETL audit records from the shared copy", flush=True)
    with sqlite3.connect(database, timeout=60) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("DELETE FROM source_records")
        connection.commit()
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("VACUUM")
        integrity = connection.execute("PRAGMA quick_check").fetchone()[0]
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "opportunities",
                "opportunity_items",
                "opportunity_documents",
                "opportunity_matches",
                "etl_runs",
                "source_records",
            )
        }
    if integrity != "ok":
        raise RuntimeError(f"SQLite integrity check failed: {integrity}")

    print(f"Compressing snapshot: {archive}", flush=True)
    with zipfile.ZipFile(
        archive,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
        allowZip64=True,
    ) as zip_file:
        zip_file.write(database, database.name)

    hasher = hashlib.sha256()
    with archive.open("rb") as archive_file:
        for chunk in iter(lambda: archive_file.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    result = {
        "source": str(source),
        "database": str(database),
        "archive": str(archive),
        "checksum": str(checksum),
        "database_bytes": database.stat().st_size,
        "archive_bytes": archive.stat().st_size,
        "sha256": digest,
        "integrity": integrity,
        "counts": counts,
        "elapsed_seconds": round(time.monotonic() - started, 2),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
