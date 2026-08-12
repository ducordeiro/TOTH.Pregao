"""SQLite persistence for ETL audit records and normalized opportunities."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import MatchResult, NormalizedOpportunity, OpportunityDocument, OpportunityItem


RADAR_STATUSES = {"new", "triage", "ignored", "selected", "converted_to_proposal"}


class ETLRepository:
    def __init__(self, database_path: str | Path, migration_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path)
        self.migration_path = Path(migration_path) if migration_path else None
        self.migrations_directory = Path(__file__).resolve().parent.parent / "migrations"

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            paths = (
                [self.migration_path]
                if self.migration_path is not None
                else sorted(self.migrations_directory.glob("*.sql"))
            )
            for path in paths:
                connection.executescript(path.read_text(encoding="utf-8"))
            self._ensure_schema_columns(connection)
            connection.commit()

    @staticmethod
    def _ensure_schema_columns(connection: sqlite3.Connection) -> None:
        item_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(opportunity_items)").fetchall()
        }
        if "granularity" not in item_columns:
            connection.execute(
                "ALTER TABLE opportunity_items ADD COLUMN granularity TEXT NOT NULL DEFAULT 'item'"
            )
        if "confidence" not in item_columns:
            connection.execute(
                "ALTER TABLE opportunity_items ADD COLUMN confidence REAL NOT NULL DEFAULT 1.0"
            )

    def create_run(
        self,
        source: str,
        run_type: str,
        filters: dict[str, Any],
    ) -> str:
        run_id = uuid.uuid4().hex
        now = _now()
        with self.connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO etl_runs (
                    id, source, run_type, status, started_at, filters_json, created_at, updated_at
                ) VALUES (?, ?, ?, 'running', ?, ?, ?, ?)
                """,
                (run_id, source, run_type, now, _json(filters), now, now),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        *,
        status: str,
        counters: dict[str, int],
        error_message: str | None = None,
    ) -> None:
        now = _now()
        with self.connect() as connection, connection:
            connection.execute(
                """
                UPDATE etl_runs SET
                    status = ?, finished_at = ?, total_fetched = ?, total_inserted = ?,
                    total_updated = ?, total_skipped = ?, total_failed = ?,
                    error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    now,
                    counters.get("fetched", 0),
                    counters.get("inserted", 0),
                    counters.get("updated", 0),
                    counters.get("skipped", 0),
                    counters.get("failed", 0),
                    error_message,
                    now,
                    run_id,
                ),
            )

    def update_run_progress(self, run_id: str, counters: dict[str, int]) -> None:
        with self.connect() as connection, connection:
            connection.execute(
                """
                UPDATE etl_runs SET
                    total_fetched = ?, total_inserted = ?, total_updated = ?,
                    total_skipped = ?, total_failed = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    counters.get("fetched", 0),
                    counters.get("inserted", 0),
                    counters.get("updated", 0),
                    counters.get("skipped", 0),
                    counters.get("failed", 0),
                    _now(),
                    run_id,
                ),
            )

    def preview_upsert(self, opportunity: NormalizedOpportunity) -> str:
        record_hash = normalized_hash(opportunity)
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT source, record_hash FROM opportunities WHERE external_key = ?",
                (opportunity.external_key,),
            ).fetchone()
        if existing is None:
            return "inserted"
        if existing["source"] == "pncp" and opportunity.source != "pncp":
            return "skipped"
        return "skipped" if existing["record_hash"] == record_hash else "updated"

    def persist_record(
        self,
        *,
        run_id: str,
        source_endpoint: str,
        request_url: str,
        raw_payload: Any,
        opportunity: NormalizedOpportunity,
        match: MatchResult,
        replace_children: bool = True,
    ) -> tuple[str, str]:
        normalized = _normalized_payload(opportunity)
        normalized_json = _json(normalized)
        record_hash = _hash_text(normalized_json)
        raw_json = _json(raw_payload)
        now = _now()
        with self.connect() as connection, connection:
            existing = connection.execute(
                "SELECT id, source, record_hash FROM opportunities WHERE external_key = ?",
                (opportunity.external_key,),
            ).fetchone()
            canonical_skip = False
            if existing is None:
                opportunity_id = uuid.uuid4().hex
                self._insert_opportunity(connection, opportunity_id, opportunity, record_hash, now)
                outcome = "inserted"
                self._replace_children(connection, opportunity_id, opportunity, now)
            else:
                opportunity_id = existing["id"]
                if existing["source"] == "pncp" and opportunity.source != "pncp":
                    outcome = "skipped"
                    canonical_skip = True
                elif existing["record_hash"] == record_hash:
                    outcome = "skipped"
                else:
                    self._update_opportunity(connection, opportunity_id, opportunity, record_hash, now)
                    if replace_children:
                        self._replace_children(connection, opportunity_id, opportunity, now)
                    outcome = "updated"
            if not canonical_skip:
                self._upsert_match(connection, opportunity_id, match, now)
            raw_hash = _hash_text(raw_json)
            run_type_row = connection.execute(
                "SELECT run_type FROM etl_runs WHERE id = ?", (run_id,)
            ).fetchone()
            duplicate_backfill_record = bool(
                run_type_row
                and run_type_row["run_type"] in {"backfill", "comprasgov_backfill"}
                and connection.execute(
                    """
                    SELECT 1 FROM source_records s
                    JOIN etl_runs r ON r.id = s.etl_run_id
                    WHERE r.run_type IN ('backfill', 'comprasgov_backfill')
                      AND s.source = ? AND s.source_endpoint = ?
                      AND s.external_key = ?
                      AND s.raw_payload_hash = ?
                    LIMIT 1
                    """,
                    (
                        opportunity.source,
                        source_endpoint,
                        opportunity.external_key,
                        raw_hash,
                    ),
                ).fetchone()
            )
            if not duplicate_backfill_record:
                connection.execute(
                    """
                    INSERT INTO source_records (
                        id, etl_run_id, opportunity_id, source, source_endpoint, request_url,
                        external_key, raw_payload_json, raw_payload_hash, normalized_payload_json,
                        normalized_payload_hash, status, captured_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        run_id,
                        opportunity_id,
                        opportunity.source,
                        source_endpoint,
                        request_url,
                        opportunity.external_key,
                        raw_json,
                        raw_hash,
                        normalized_json,
                        record_hash,
                        outcome,
                        now,
                        now,
                    ),
                )
        return outcome, opportunity_id

    def save_failed_source_record(
        self,
        *,
        run_id: str,
        source: str,
        source_endpoint: str,
        request_url: str,
        raw_payload: Any,
        error_message: str,
        external_key: str | None = None,
    ) -> None:
        raw_json = _json(raw_payload)
        now = _now()
        with self.connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO source_records (
                    id, etl_run_id, source, source_endpoint, request_url, external_key,
                    raw_payload_json, raw_payload_hash, status, error_message, captured_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'failed', ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    run_id,
                    source,
                    source_endpoint,
                    request_url,
                    external_key,
                    raw_json,
                    _hash_text(raw_json),
                    error_message[:2000],
                    now,
                    now,
                ),
            )

    def list_opportunities(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        filters = filters or {}
        where: list[str] = []
        params: list[Any] = []
        profile_id = str(filters.get("company_profile_id") or "default")
        radar_status = filters.get("radar_status")
        if radar_status:
            statuses = _as_list(radar_status)
            where.append(f"o.radar_status IN ({','.join('?' for _ in statuses)})")
            params.extend(statuses)
        score_min = _float(filters.get("score_min"))
        if score_min is not None:
            where.append("COALESCE(m.score, 0) >= ?")
            params.append(score_min)
        ufs = [value.upper() for value in _as_list(filters.get("uf") or filters.get("ufs"))]
        if ufs:
            where.append(f"o.uf IN ({','.join('?' for _ in ufs)})")
            params.extend(ufs)
        if filters.get("city"):
            where.append("LOWER(o.city) = LOWER(?)")
            params.append(str(filters["city"]))
        if filters.get("modality"):
            where.append("LOWER(o.modality) LIKE LOWER(?)")
            params.append(f"%{filters['modality']}%")
        modality_code = _integer(filters.get("modality_code"))
        if modality_code is not None:
            where.append("o.modality_code = ?")
            params.append(modality_code)
        if filters.get("uasg"):
            where.append("LTRIM(COALESCE(o.uasg, ''), '0') = LTRIM(?, '0')")
            params.append(str(filters["uasg"]))
        if filters.get("purchase_number"):
            purchase_number = f"%{filters['purchase_number']}%"
            where.append("(o.title LIKE ? OR o.process_number LIKE ? OR o.pncp_control_number LIKE ?)")
            params.extend([purchase_number, purchase_number, purchase_number])
        if filters.get("published_from"):
            where.append("o.published_at >= ?")
            params.append(filters["published_from"])
        if filters.get("published_to"):
            where.append("o.published_at <= ?")
            params.append(filters["published_to"])
        if filters.get("proposal_open"):
            where.append("(o.proposal_end_at IS NULL OR o.proposal_end_at >= ?)")
            params.append(_now())
        if filters.get("proposal_from"):
            where.append("o.proposal_end_at >= ?")
            params.append(filters["proposal_from"])
        if filters.get("proposal_to"):
            where.append("o.proposal_end_at <= ?")
            params.append(filters["proposal_to"])
        keywords = _as_list(filters.get("keywords"))
        if keywords:
            alternatives = []
            for keyword in keywords:
                query = f"%{keyword}%"
                alternatives.append(
                    "(o.title LIKE ? OR o.description LIKE ? OR o.buyer_name LIKE ? "
                    "OR EXISTS (SELECT 1 FROM opportunity_items oi "
                    "WHERE oi.opportunity_id = o.id AND (oi.title LIKE ? OR oi.description LIKE ?)))"
                )
                params.extend([query, query, query, query, query])
            where.append(f"({' OR '.join(alternatives)})")
        object_type = str(filters.get("object_type") or "").lower()
        if object_type == "material":
            where.append(
                "EXISTS (SELECT 1 FROM opportunity_items oi WHERE oi.opportunity_id = o.id "
                "AND LOWER(oi.title) LIKE '%material%')"
            )
        elif object_type == "servico":
            where.append(
                "EXISTS (SELECT 1 FROM opportunity_items oi WHERE oi.opportunity_id = o.id "
                "AND (LOWER(oi.title) LIKE '%servi%' OR LOWER(oi.title) LIKE '%service%'))"
            )
        if filters.get("q"):
            query = f"%{filters['q']}%"
            where.append(
                "(o.title LIKE ? OR o.description LIKE ? OR o.buyer_name LIKE ? OR o.process_number LIKE ?)"
            )
            params.extend([query, query, query, query])
        limit = min(max(_integer(filters.get("limit")) or 50, 1), 500)
        offset = max(_integer(filters.get("offset")) or 0, 0)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        join_params = [profile_id]
        with self.connect() as connection:
            total = connection.execute(
                f"""
                SELECT COUNT(*) FROM opportunities o
                LEFT JOIN opportunity_matches m
                  ON m.opportunity_id = o.id AND m.company_profile_id = ?
                {clause}
                """,
                join_params + params,
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT o.*, COALESCE(m.score, 0) AS score, m.reasons_json
                FROM opportunities o
                LEFT JOIN opportunity_matches m
                  ON m.opportunity_id = o.id AND m.company_profile_id = ?
                {clause}
                ORDER BY COALESCE(m.score, 0) DESC,
                         CASE WHEN o.proposal_end_at IS NULL THEN 1 ELSE 0 END,
                         o.proposal_end_at ASC, o.published_at DESC
                LIMIT ? OFFSET ?
                """,
                join_params + params + [limit, offset],
            ).fetchall()
        items = [_row(row) for row in rows]
        for item in items:
            item["reasons"] = _decode_json(item.pop("reasons_json", None), [])
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get_opportunity(self, opportunity_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            opportunity = connection.execute(
                "SELECT * FROM opportunities WHERE id = ?", (opportunity_id,)
            ).fetchone()
            if opportunity is None:
                return None
            items = connection.execute(
                """
                SELECT * FROM opportunity_items WHERE opportunity_id = ?
                ORDER BY lot_number, CAST(item_number AS INTEGER), item_number
                """,
                (opportunity_id,),
            ).fetchall()
            documents = connection.execute(
                "SELECT * FROM opportunity_documents WHERE opportunity_id = ? ORDER BY created_at, title",
                (opportunity_id,),
            ).fetchall()
            matches = connection.execute(
                "SELECT * FROM opportunity_matches WHERE opportunity_id = ? ORDER BY score DESC",
                (opportunity_id,),
            ).fetchall()
        match_values = [_row(row) for row in matches]
        for match in match_values:
            for field in (
                "matched_keywords_json",
                "matched_items_json",
                "matched_regions_json",
                "matched_modalities_json",
                "reasons_json",
            ):
                match[field.removesuffix("_json")] = _decode_json(match.pop(field), [])
        return {
            "opportunity": _row(opportunity),
            "items": [_row(row) for row in items],
            "documents": [_row(row) for row in documents],
            "matches": match_values,
        }

    def get_opportunity_by_pncp_identity(
        self, cnpj: str, year: int, sequence: int
    ) -> dict[str, Any] | None:
        """Return normalized opportunity data using the identity encoded in a PNCP URL."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT id FROM opportunities
                WHERE source_cnpj = ? AND year = ? AND sequence = ?
                ORDER BY CASE WHEN source = 'pncp' THEN 0 ELSE 1 END, updated_at DESC
                LIMIT 1
                """,
                (str(cnpj), int(year), int(sequence)),
            ).fetchone()
        return self.get_opportunity(row["id"]) if row else None

    def list_runs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        limit = min(max(int(limit), 1), 500)
        offset = max(int(offset), 0)
        with self.connect() as connection:
            total = connection.execute("SELECT COUNT(*) FROM etl_runs").fetchone()[0]
            rows = connection.execute(
                "SELECT * FROM etl_runs ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        result = [_row(row) for row in rows]
        for row in result:
            row["filters"] = _decode_json(row.pop("filters_json"), {})
        return {"items": result, "total": total, "limit": limit, "offset": offset}

    def get_backfill_checkpoint(
        self,
        *,
        source: str,
        endpoint: str,
        date_from: str,
        date_to: str,
        modality_code: int,
    ) -> dict[str, Any] | None:
        scope_key = _backfill_scope_key(
            source, endpoint, date_from, date_to, modality_code
        )
        with self.connect() as connection:
            row = connection.execute(
                "SELECT next_page, completed FROM backfill_checkpoints WHERE scope_key = ?",
                (scope_key,),
            ).fetchone()
        if row is None:
            return None
        return {
            "next_page": max(1, int(row["next_page"])),
            "completed": bool(row["completed"]),
        }

    def has_covering_backfill_checkpoint(
        self,
        *,
        source: str,
        endpoint: str,
        date_from: str,
        date_to: str,
        modality_code: int,
    ) -> bool:
        """Return whether a completed broader window fully covers this unit."""
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM backfill_checkpoints
                WHERE source = ? AND endpoint = ? AND modality_code = ?
                  AND completed = 1 AND date_from <= ? AND date_to >= ?
                LIMIT 1
                """,
                (source, endpoint, int(modality_code), date_from, date_to),
            ).fetchone()
        return row is not None

    def save_backfill_checkpoint(
        self,
        *,
        source: str,
        endpoint: str,
        date_from: str,
        date_to: str,
        modality_code: int,
        next_page: int,
        completed: bool = False,
    ) -> None:
        scope_key = _backfill_scope_key(
            source, endpoint, date_from, date_to, modality_code
        )
        now = _now()
        with self.connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO backfill_checkpoints (
                    scope_key, source, endpoint, date_from, date_to, modality_code,
                    next_page, completed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_key) DO UPDATE SET
                    next_page = MAX(backfill_checkpoints.next_page, excluded.next_page),
                    completed = MAX(backfill_checkpoints.completed, excluded.completed),
                    updated_at = excluded.updated_at
                """,
                (
                    scope_key,
                    source,
                    endpoint,
                    date_from,
                    date_to,
                    int(modality_code),
                    max(1, int(next_page)),
                    int(bool(completed)),
                    now,
                    now,
                ),
            )

    def recover_backfill_next_page(
        self,
        *,
        source: str,
        run_type: str,
        date_from: str,
        date_to: str,
        modality_code: int,
    ) -> int:
        """Recover the first unprocessed page from legacy failed backfill runs."""
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT r.filters_json, s.request_url
                FROM etl_runs r
                JOIN source_records s ON s.etl_run_id = r.id
                WHERE r.source = ? AND r.run_type = ?
                """,
                (source, run_type),
            ).fetchall()

        expected_start = date_from.replace("-", "")
        expected_end = date_to.replace("-", "")
        highest_page = 0
        for row in rows:
            filters = _decode_json(row["filters_json"], {})
            queries = filters.get("queries") if isinstance(filters, dict) else None
            if not isinstance(queries, list) or len(queries) != 1:
                continue
            query = queries[0]
            if not isinstance(query, dict):
                continue
            if str(query.get("dataInicial") or "") != expected_start:
                continue
            if str(query.get("dataFinal") or "") != expected_end:
                continue
            if _integer(query.get("codigoModalidadeContratacao")) != int(modality_code):
                continue
            parsed = urllib.parse.urlparse(str(row["request_url"] or ""))
            page_values = urllib.parse.parse_qs(parsed.query).get("pagina", [])
            if page_values:
                highest_page = max(highest_page, _integer(page_values[0]) or 0)
        return highest_page + 1

    def has_completed_checkpoint(
        self,
        *,
        source: str,
        run_type: str,
        target_date: str,
        target_end_date: str | None = None,
        modality_code: int,
        dry_run: bool,
        max_pages: int | None,
        max_records: int | None,
        fetch_details: bool,
    ) -> bool:
        """Return whether an equivalent backfill unit already completed safely."""
        statuses = ("success", "dry_run") if dry_run else ("success",)
        placeholders = ",".join("?" for _ in statuses)
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT status, filters_json, total_failed
                FROM etl_runs
                WHERE source = ? AND run_type = ?
                  AND status IN ({placeholders})
                ORDER BY started_at DESC
                """,
                (source, run_type, *statuses),
            ).fetchall()

        pncp_date = target_date.replace("-", "")
        pncp_end_date = (target_end_date or target_date).replace("-", "")
        for row in rows:
            if int(row["total_failed"] or 0) != 0:
                continue
            filters = _decode_json(row["filters_json"], {})
            queries = filters.get("queries") if isinstance(filters, dict) else None
            if not isinstance(queries, list) or len(queries) != 1:
                continue
            query = queries[0]
            if not isinstance(query, dict):
                continue
            if str(query.get("dataInicial") or "") != pncp_date:
                continue
            if str(query.get("dataFinal") or "") != pncp_end_date:
                continue
            if _integer(query.get("codigoModalidadeContratacao")) != modality_code:
                continue
            if not _checkpoint_limit_covers(filters.get("max_pages"), max_pages):
                continue
            if not _checkpoint_limit_covers(filters.get("max_records"), max_records):
                continue
            if fetch_details and not bool(filters.get("fetch_details")):
                continue
            return True
        return False

    def update_radar_status(
        self,
        opportunity_id: str,
        radar_status: str,
        converted_business_id: int | None = None,
    ) -> bool:
        if radar_status not in RADAR_STATUSES:
            raise ValueError(f"invalid radar_status: {radar_status}")
        with self.connect() as connection, connection:
            cursor = connection.execute(
                """
                UPDATE opportunities
                SET radar_status = ?, converted_business_id = COALESCE(?, converted_business_id), updated_at = ?
                WHERE id = ?
                """,
                (radar_status, converted_business_id, _now(), opportunity_id),
            )
        return cursor.rowcount > 0

    def replace_opportunity_documents(
        self,
        opportunity_id: str,
        documents: list[OpportunityDocument],
    ) -> int:
        now = _now()
        with self.connect() as connection, connection:
            exists = connection.execute(
                "SELECT 1 FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(f"opportunity not found: {opportunity_id}")
            connection.execute(
                "DELETE FROM opportunity_documents WHERE opportunity_id = ?",
                (opportunity_id,),
            )
            for document in documents:
                connection.execute(
                    """
                    INSERT INTO opportunity_documents (
                        id, opportunity_id, document_type, title, url, filename, mime_type,
                        source, download_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        opportunity_id,
                        document.document_type,
                        document.title,
                        document.url,
                        document.filename,
                        document.mime_type,
                        document.source,
                        document.download_status,
                        now,
                        now,
                    ),
                )
            connection.execute(
                "UPDATE opportunities SET updated_at = ? WHERE id = ?",
                (now, opportunity_id),
            )
        return len(documents)

    def replace_opportunity_items(
        self,
        opportunity_id: str,
        items: list[OpportunityItem],
    ) -> int:
        now = _now()
        with self.connect() as connection, connection:
            exists = connection.execute(
                "SELECT 1 FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
            if exists is None:
                raise KeyError(f"opportunity not found: {opportunity_id}")
            connection.execute(
                "DELETE FROM opportunity_items WHERE opportunity_id = ?",
                (opportunity_id,),
            )
            self._insert_items(connection, opportunity_id, items, now)
            connection.execute(
                "UPDATE opportunities SET updated_at = ? WHERE id = ?",
                (now, opportunity_id),
            )
        return len(items)

    @staticmethod
    def _insert_opportunity(
        connection: sqlite3.Connection,
        opportunity_id: str,
        opportunity: NormalizedOpportunity,
        record_hash: str,
        now: str,
    ) -> None:
        values = _opportunity_values(opportunity)
        connection.execute(
            f"""
            INSERT INTO opportunities (
                id, {', '.join(values)}, record_hash, radar_status, created_at, updated_at
            ) VALUES (?, {', '.join('?' for _ in values)}, ?, 'new', ?, ?)
            """,
            [opportunity_id, *values.values(), record_hash, now, now],
        )

    @staticmethod
    def _update_opportunity(
        connection: sqlite3.Connection,
        opportunity_id: str,
        opportunity: NormalizedOpportunity,
        record_hash: str,
        now: str,
    ) -> None:
        values = _opportunity_values(opportunity)
        assignments = ", ".join(f"{column} = ?" for column in values)
        connection.execute(
            f"UPDATE opportunities SET {assignments}, record_hash = ?, updated_at = ? WHERE id = ?",
            [*values.values(), record_hash, now, opportunity_id],
        )

    @staticmethod
    def _replace_children(
        connection: sqlite3.Connection,
        opportunity_id: str,
        opportunity: NormalizedOpportunity,
        now: str,
    ) -> None:
        connection.execute("DELETE FROM opportunity_items WHERE opportunity_id = ?", (opportunity_id,))
        connection.execute("DELETE FROM opportunity_documents WHERE opportunity_id = ?", (opportunity_id,))
        ETLRepository._insert_items(connection, opportunity_id, opportunity.items, now)
        for document in opportunity.documents:
            connection.execute(
                """
                INSERT INTO opportunity_documents (
                    id, opportunity_id, document_type, title, url, filename, mime_type,
                    source, download_status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    opportunity_id,
                    document.document_type,
                    document.title,
                    document.url,
                    document.filename,
                    document.mime_type,
                    document.source,
                    document.download_status,
                    now,
                    now,
                ),
            )

    @staticmethod
    def _insert_items(
        connection: sqlite3.Connection,
        opportunity_id: str,
        items: list[OpportunityItem],
        now: str,
    ) -> None:
        for item in items:
            connection.execute(
                """
                INSERT INTO opportunity_items (
                    id, opportunity_id, source_item_id, lot_number, item_number, title,
                    description, technical_object, quantity, unit, estimated_unit_value,
                    estimated_total_value, currency, status, granularity, confidence,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    opportunity_id,
                    item.source_item_id,
                    item.lot_number,
                    item.item_number,
                    item.title,
                    item.description,
                    item.technical_object,
                    item.quantity,
                    item.unit,
                    item.estimated_unit_value,
                    item.estimated_total_value,
                    item.currency,
                    item.status,
                    item.granularity,
                    item.confidence,
                    now,
                    now,
                ),
            )

    @staticmethod
    def _upsert_match(
        connection: sqlite3.Connection,
        opportunity_id: str,
        match: MatchResult,
        now: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO opportunity_matches (
                id, opportunity_id, company_profile_id, score, matched_keywords_json,
                matched_items_json, matched_regions_json, matched_modalities_json,
                reasons_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_id, company_profile_id) DO UPDATE SET
                score = excluded.score,
                matched_keywords_json = excluded.matched_keywords_json,
                matched_items_json = excluded.matched_items_json,
                matched_regions_json = excluded.matched_regions_json,
                matched_modalities_json = excluded.matched_modalities_json,
                reasons_json = excluded.reasons_json,
                updated_at = excluded.updated_at
            """,
            (
                uuid.uuid4().hex,
                opportunity_id,
                match.company_profile_id,
                match.score,
                _json(match.matched_keywords),
                _json(match.matched_items),
                _json(match.matched_regions),
                _json(match.matched_modalities),
                _json(match.reasons),
                now,
                now,
            ),
        )


def normalized_hash(opportunity: NormalizedOpportunity) -> str:
    return _hash_text(_json(_normalized_payload(opportunity)))


def _normalized_payload(opportunity: NormalizedOpportunity) -> dict[str, Any]:
    payload = opportunity.to_dict()
    payload["items"] = sorted(
        payload["items"],
        key=lambda item: (str(item.get("lot_number") or ""), str(item.get("item_number") or "")),
    )
    payload["documents"] = sorted(
        payload["documents"], key=lambda document: str(document.get("url") or "")
    )
    return payload


def _opportunity_values(opportunity: NormalizedOpportunity) -> dict[str, Any]:
    return {
        "external_key": opportunity.external_key,
        "source": opportunity.source,
        "pncp_control_number": opportunity.pncp_control_number,
        "source_cnpj": opportunity.source_cnpj,
        "year": opportunity.year,
        "sequence": opportunity.sequence,
        "process_number": opportunity.process_number,
        "title": opportunity.title,
        "description": opportunity.description,
        "buyer_name": opportunity.buyer_name,
        "buyer_cnpj": opportunity.buyer_cnpj,
        "uf": opportunity.uf,
        "city": opportunity.city,
        "uasg": opportunity.uasg,
        "modality": opportunity.modality,
        "modality_code": opportunity.modality_code,
        "status": opportunity.status,
        "estimated_value": opportunity.estimated_value,
        "currency": opportunity.currency,
        "published_at": opportunity.published_at,
        "proposal_start_at": opportunity.proposal_start_at,
        "proposal_end_at": opportunity.proposal_end_at,
        "source_url": opportunity.source_url,
        "detail_url": opportunity.detail_url,
        "origin_url": opportunity.origin_url,
    }


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _decode_json(value: str | None, default: Any) -> Any:
    try:
        return json.loads(value) if value else default
    except (TypeError, json.JSONDecodeError):
        return default


def _as_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    values = value if isinstance(value, (list, tuple, set)) else str(value).split(",")
    return [str(item).strip() for item in values if str(item).strip()]


def _integer(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _checkpoint_limit_covers(previous: Any, requested: int | None) -> bool:
    previous_limit = _integer(previous)
    if requested is None:
        return previous is None
    return previous is None or (previous_limit is not None and previous_limit >= requested)


def _backfill_scope_key(
    source: str,
    endpoint: str,
    date_from: str,
    date_to: str,
    modality_code: int,
) -> str:
    return _hash_text(_json({
        "source": source,
        "endpoint": endpoint,
        "date_from": date_from,
        "date_to": date_to,
        "modality_code": int(modality_code),
    }))
