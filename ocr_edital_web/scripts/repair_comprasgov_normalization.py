"""Repair normalized Compras.gov metadata from the preserved raw payloads."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from etl.mappers import ComprasGovMapper


def repair(database_path: Path, batch_size: int = 1_000) -> tuple[int, int]:
    connection = sqlite3.connect(database_path, timeout=60)
    connection.row_factory = sqlite3.Row
    mapper = ComprasGovMapper()
    repaired = 0
    failed = 0
    pending: list[tuple[object, ...]] = []
    rows = connection.execute(
        """
        SELECT o.id, sr.raw_payload_json
        FROM opportunities o
        JOIN source_records sr ON sr.opportunity_id = o.id
        WHERE o.source = 'comprasgov'
          AND (o.modality_code IS NULL OR o.buyer_cnpj IS NULL OR o.uf IS NULL OR o.year IS NULL)
          AND sr.source = 'comprasgov'
          AND sr.id = (
              SELECT latest.id
              FROM source_records latest
              WHERE latest.opportunity_id = o.id AND latest.source = 'comprasgov'
              ORDER BY latest.captured_at DESC, latest.created_at DESC
              LIMIT 1
          )
        ORDER BY o.id
        """
    )
    for row in rows:
        try:
            envelope = json.loads(row["raw_payload_json"])
            payload = envelope.get("listing", envelope)
            opportunity = mapper.map(payload)
            pending.append((
                opportunity.source_cnpj,
                opportunity.year,
                opportunity.sequence,
                opportunity.buyer_name,
                opportunity.buyer_cnpj,
                opportunity.uf,
                opportunity.city,
                opportunity.uasg,
                opportunity.modality,
                opportunity.modality_code,
                opportunity.status,
                opportunity.proposal_start_at,
                opportunity.proposal_end_at,
                opportunity.detail_url,
                datetime.now().astimezone().isoformat(timespec="seconds"),
                row["id"],
            ))
        except (TypeError, ValueError, json.JSONDecodeError):
            failed += 1
            continue
        if len(pending) >= batch_size:
            repaired += _flush(connection, pending)
    repaired += _flush(connection, pending)
    connection.close()
    return repaired, failed


def _flush(connection: sqlite3.Connection, pending: list[tuple[object, ...]]) -> int:
    if not pending:
        return 0
    connection.executemany(
        """
        UPDATE opportunities SET
            source_cnpj = COALESCE(source_cnpj, ?),
            year = COALESCE(year, ?),
            sequence = COALESCE(sequence, ?),
            buyer_name = COALESCE(buyer_name, ?),
            buyer_cnpj = COALESCE(buyer_cnpj, ?),
            uf = COALESCE(uf, ?),
            city = COALESCE(city, ?),
            uasg = COALESCE(uasg, ?),
            modality = COALESCE(modality, ?),
            modality_code = COALESCE(modality_code, ?),
            status = COALESCE(status, ?),
            proposal_start_at = COALESCE(proposal_start_at, ?),
            proposal_end_at = COALESCE(proposal_end_at, ?),
            detail_url = COALESCE(detail_url, ?),
            updated_at = ?
        WHERE id = ?
        """,
        pending,
    )
    count = len(pending)
    connection.commit()
    pending.clear()
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("--batch-size", type=int, default=1_000)
    args = parser.parse_args()
    repaired, failed = repair(args.database, args.batch_size)
    print(json.dumps({"repaired": repaired, "failed": failed}))


if __name__ == "__main__":
    main()
