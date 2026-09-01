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
from .search_filters import (
    build_fts_query,
    classify_object_text,
    fold_search_text,
    is_single_word_search_term,
    search_term_matches,
)


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
        connection.create_function("fold_search_text", 1, fold_search_text, deterministic=True)
        connection.create_function("classify_object_text", 1, classify_object_text, deterministic=True)
        connection.create_function(
            "search_term_matches", 2, search_term_matches, deterministic=True
        )
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
        classification_columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(opportunity_object_classifications)"
            ).fetchall()
        }
        classification_changed = False
        if "matches_material" not in classification_columns:
            connection.execute(
                """
                ALTER TABLE opportunity_object_classifications
                ADD COLUMN matches_material INTEGER NOT NULL DEFAULT 0
                CHECK (matches_material IN (0, 1))
                """
            )
            classification_changed = True
        if "matches_service" not in classification_columns:
            connection.execute(
                """
                ALTER TABLE opportunity_object_classifications
                ADD COLUMN matches_service INTEGER NOT NULL DEFAULT 0
                CHECK (matches_service IN (0, 1))
                """
            )
            classification_changed = True
        if classification_changed:
            connection.execute(
                """
                UPDATE opportunity_object_classifications
                SET
                    matches_material = CASE WHEN (
                        opportunity_type = 'material'
                        OR has_material = 1
                        OR (
                            opportunity_type = 'unclassified'
                            AND has_material = 0
                            AND has_service = 0
                        )
                    ) THEN 1 ELSE 0 END,
                    matches_service = CASE WHEN (
                        opportunity_type = 'servico'
                        OR has_service = 1
                        OR (
                            opportunity_type = 'unclassified'
                            AND has_material = 0
                            AND has_service = 0
                        )
                    ) THEN 1 ELSE 0 END
                """
            )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_opportunity_object_matches_material
            ON opportunity_object_classifications(matches_material, opportunity_id)
            WHERE matches_material = 1
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_opportunity_object_matches_service
            ON opportunity_object_classifications(matches_service, opportunity_id)
            WHERE matches_service = 1
            """
        )
        opportunity_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(opportunities)").fetchall()
        }
        if "search_aliases" not in opportunity_columns:
            connection.execute(
                "ALTER TABLE opportunities ADD COLUMN search_aliases TEXT NOT NULL DEFAULT ''"
            )
            opportunity_columns.add("search_aliases")
        search_triggers = {
            row["name"]: row["sql"] or ""
            for row in connection.execute(
                """
                SELECT name, sql FROM sqlite_master
                WHERE type = 'trigger'
                  AND name IN ('opportunities_search_ai', 'opportunities_search_au')
                """
            ).fetchall()
        }
        if any(
            "search_aliases" not in search_triggers.get(trigger_name, "")
            for trigger_name in ("opportunities_search_ai", "opportunities_search_au")
        ):
            connection.executescript(
                """
                DROP TRIGGER IF EXISTS opportunities_search_ai;
                DROP TRIGGER IF EXISTS opportunities_search_au;

                CREATE TRIGGER opportunities_search_ai AFTER INSERT ON opportunities BEGIN
                  INSERT OR REPLACE INTO opportunity_search(rowid, opportunity_id, content)
                  VALUES (
                    NEW.rowid,
                    NEW.id,
                    TRIM(
                      COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.description, '') || ' ' ||
                      COALESCE(NEW.buyer_name, '') || ' ' || COALESCE(NEW.city, '') || ' ' ||
                      COALESCE(NEW.modality, '') || ' ' || COALESCE(NEW.process_number, '') || ' ' ||
                      COALESCE(NEW.pncp_control_number, '') || ' ' || COALESCE(NEW.uasg, '') || ' ' ||
                      COALESCE(NEW.status, '') || ' ' || COALESCE(NEW.search_aliases, '')
                    )
                  );
                END;

                CREATE TRIGGER opportunities_search_au AFTER UPDATE ON opportunities BEGIN
                  DELETE FROM opportunity_search WHERE rowid = OLD.rowid;
                  INSERT INTO opportunity_search(rowid, opportunity_id, content)
                  SELECT
                    o.rowid,
                    o.id,
                    TRIM(
                      COALESCE(o.title, '') || ' ' || COALESCE(o.description, '') || ' ' ||
                      COALESCE(o.buyer_name, '') || ' ' || COALESCE(o.city, '') || ' ' ||
                      COALESCE(o.modality, '') || ' ' || COALESCE(o.process_number, '') || ' ' ||
                      COALESCE(o.pncp_control_number, '') || ' ' || COALESCE(o.uasg, '') || ' ' ||
                      COALESCE(o.status, '') || ' ' || COALESCE(o.search_aliases, '') || ' ' ||
                      COALESCE((SELECT GROUP_CONCAT(COALESCE(oi.source_item_id, '') || ' ' || COALESCE(oi.lot_number, '') || ' ' || COALESCE(oi.item_number, '') || ' ' || COALESCE(oi.title, '') || ' ' || COALESCE(oi.description, '') || ' ' || COALESCE(oi.technical_object, '') || ' ' || COALESCE(oi.unit, '') || ' ' || COALESCE(oi.status, ''), ' ') FROM opportunity_items oi WHERE oi.opportunity_id = o.id), '') || ' ' ||
                      COALESCE((SELECT GROUP_CONCAT(COALESCE(od.document_type, '') || ' ' || COALESCE(od.title, '') || ' ' || COALESCE(od.filename, ''), ' ') FROM opportunity_documents od WHERE od.opportunity_id = o.id), '')
                    )
                  FROM opportunities o WHERE o.id = NEW.id;
                END;
                """
            )
        opportunity_matches_changed = False
        if "object_matches_material" not in opportunity_columns:
            connection.execute(
                """
                ALTER TABLE opportunities
                ADD COLUMN object_matches_material INTEGER NOT NULL DEFAULT 1
                CHECK (object_matches_material IN (0, 1))
                """
            )
            opportunity_matches_changed = True
        if "object_matches_service" not in opportunity_columns:
            connection.execute(
                """
                ALTER TABLE opportunities
                ADD COLUMN object_matches_service INTEGER NOT NULL DEFAULT 1
                CHECK (object_matches_service IN (0, 1))
                """
            )
            opportunity_matches_changed = True
        if opportunity_matches_changed:
            update_trigger = connection.execute(
                """
                SELECT sql FROM sqlite_master
                WHERE type = 'trigger' AND name = 'opportunities_search_au'
                """
            ).fetchone()
            connection.execute("DROP TRIGGER IF EXISTS opportunities_search_au")
            try:
                connection.execute(
                    """
                    UPDATE opportunities
                    SET
                        object_matches_material = COALESCE((
                            SELECT matches_material
                            FROM opportunity_object_classifications classification
                            WHERE classification.opportunity_id = opportunities.id
                        ), 1),
                        object_matches_service = COALESCE((
                            SELECT matches_service
                            FROM opportunity_object_classifications classification
                            WHERE classification.opportunity_id = opportunities.id
                        ), 1)
                    """
                )
            finally:
                if update_trigger and update_trigger["sql"]:
                    connection.execute(update_trigger["sql"])
        for object_type in ("material", "service"):
            column = f"object_matches_{object_type}"
            for suffix, date_column in (
                ("published", "published_at"),
                ("proposal_start", "proposal_start_at"),
                ("proposal_end", "proposal_end_at"),
            ):
                connection.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS idx_opportunities_{object_type}_{suffix}
                    ON opportunities(
                        {column}, {date_column}, radar_status, modality_code, uf
                    )
                    """
                )
            connection.execute(
                f"""
                CREATE INDEX IF NOT EXISTS idx_opportunities_{object_type}_missing_end_published
                ON opportunities(
                    {column}, published_at, radar_status, modality_code, uf
                )
                WHERE proposal_end_at IS NULL OR proposal_end_at = ''
                """
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
        replace_items: bool | None = None,
        replace_documents: bool | None = None,
    ) -> tuple[str, str]:
        should_replace_items = replace_children if replace_items is None else replace_items
        should_replace_documents = (
            replace_children if replace_documents is None else replace_documents
        )
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
                    if should_replace_items:
                        self._replace_items(connection, opportunity_id, opportunity.items, now)
                    if should_replace_documents:
                        self._replace_documents(
                            connection, opportunity_id, opportunity.documents, now
                        )
                    if not should_replace_items:
                        self._refresh_object_classification(connection, opportunity_id, now)
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

    def add_opportunity_search_terms(
        self,
        opportunity_id: str,
        search_terms: list[str] | tuple[str, ...],
    ) -> bool:
        cleaned_terms = []
        seen = set()
        for value in search_terms:
            term = " ".join(str(value or "").split()).strip()
            folded = fold_search_text(term)
            if not folded or folded in seen:
                continue
            seen.add(folded)
            cleaned_terms.append(term[:120])
        if not cleaned_terms:
            return False

        with self.connect() as connection, connection:
            row = connection.execute(
                "SELECT search_aliases FROM opportunities WHERE id = ?",
                (opportunity_id,),
            ).fetchone()
            if row is None:
                return False
            existing_terms = [
                value.strip()
                for value in str(row["search_aliases"] or "").splitlines()
                if value.strip()
            ]
            existing_folded = {fold_search_text(value) for value in existing_terms}
            additions = [
                value
                for value in cleaned_terms
                if fold_search_text(value) not in existing_folded
            ]
            if not additions:
                return False
            aliases = "\n".join([*existing_terms, *additions])[:4000]
            connection.execute(
                "UPDATE opportunities SET search_aliases = ? WHERE id = ?",
                (aliases, opportunity_id),
            )
        return True

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

    def save_successful_source_record(
        self,
        *,
        run_id: str,
        opportunity_id: str,
        source: str,
        source_endpoint: str,
        request_url: str,
        raw_payload: Any,
        external_key: str | None = None,
    ) -> None:
        raw_json = _json(raw_payload)
        now = _now()
        with self.connect() as connection, connection:
            connection.execute(
                """
                INSERT INTO source_records (
                    id, etl_run_id, opportunity_id, source, source_endpoint, request_url,
                    external_key, raw_payload_json, raw_payload_hash, status, captured_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'success', ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    run_id,
                    opportunity_id,
                    source,
                    source_endpoint,
                    request_url,
                    external_key,
                    raw_json,
                    _hash_text(raw_json),
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
            purchase_number = _like_pattern(filters["purchase_number"])
            where.append(
                "(fold_search_text(o.title) LIKE ? ESCAPE '\\' "
                "OR fold_search_text(o.process_number) LIKE ? ESCAPE '\\' "
                "OR fold_search_text(o.pncp_control_number) LIKE ? ESCAPE '\\')"
            )
            params.extend([purchase_number, purchase_number, purchase_number])
        if filters.get("published_from"):
            where.append("o.published_at >= ?")
            params.append(_date_lower_bound(filters["published_from"]))
        if filters.get("published_to"):
            where.append("o.published_at <= ?")
            params.append(filters["published_to"])
        if filters.get("proposal_start_from"):
            where.append("o.proposal_start_at >= ?")
            params.append(_date_lower_bound(filters["proposal_start_from"]))
        if filters.get("proposal_start_to"):
            where.append("o.proposal_start_at <= ?")
            params.append(filters["proposal_start_to"])
        if filters.get("proposal_open"):
            where.append("(o.proposal_end_at IS NULL OR o.proposal_end_at >= ?)")
            params.append(_now())
        keywords = _as_list(filters.get("keywords"))
        include_missing_proposal_dates = bool(filters.get("include_missing_proposal_dates"))
        date_union_bounds: tuple[str, Any] | None = None
        proposal_from = filters.get("proposal_from")
        proposal_to = filters.get("proposal_to")
        if proposal_from and proposal_to and include_missing_proposal_dates:
            lower_bound = _date_lower_bound(proposal_from)
            if score_min is None and not filters.get("sort_by_score") and not keywords:
                date_union_bounds = (lower_bound, proposal_to)
            else:
                where.append(
                    "(((o.proposal_end_at IS NOT NULL AND o.proposal_end_at <> '') "
                    "AND o.proposal_end_at >= ? AND o.proposal_end_at <= ?) OR "
                    "((o.proposal_end_at IS NULL OR o.proposal_end_at = '') "
                    "AND o.published_at >= ? AND o.published_at <= ?))"
                )
                params.extend([lower_bound, proposal_to, lower_bound, proposal_to])
        elif proposal_from:
            if include_missing_proposal_dates:
                where.append(
                    "(o.proposal_end_at >= ? OR "
                    "((o.proposal_end_at IS NULL OR o.proposal_end_at = '') "
                    "AND o.published_at >= ?))"
                )
                lower_bound = _date_lower_bound(proposal_from)
                params.extend([lower_bound, lower_bound])
            else:
                where.append("o.proposal_end_at >= ?")
                params.append(_date_lower_bound(proposal_from))
        if proposal_to and not (proposal_from and include_missing_proposal_dates):
            if include_missing_proposal_dates:
                where.append(
                    "(o.proposal_end_at <= ? OR "
                    "((o.proposal_end_at IS NULL OR o.proposal_end_at = '') "
                    "AND o.published_at <= ?))"
                )
                params.extend([proposal_to, proposal_to])
            else:
                where.append("o.proposal_end_at <= ?")
                params.append(proposal_to)
        fts_query = ""
        if keywords:
            fts_query = build_fts_query(keywords)
            if fts_query:
                where.append("opportunity_search MATCH ?")
                params.append(fts_query)
            if not all(is_single_word_search_term(keyword) for keyword in keywords):
                opportunity_search_text = " || ' ' || ".join((
                    "COALESCE(o.title, '')",
                    "COALESCE(o.description, '')",
                    "COALESCE(o.buyer_name, '')",
                    "COALESCE(o.city, '')",
                    "COALESCE(o.modality, '')",
                    "COALESCE(o.process_number, '')",
                    "COALESCE(o.pncp_control_number, '')",
                    "COALESCE(o.uasg, '')",
                    "COALESCE(o.status, '')",
                    "COALESCE(o.search_aliases, '')",
                ))
                item_search_text = " || ' ' || ".join((
                    "COALESCE(oi.source_item_id, '')",
                    "COALESCE(oi.lot_number, '')",
                    "COALESCE(oi.item_number, '')",
                    "COALESCE(oi.title, '')",
                    "COALESCE(oi.description, '')",
                    "COALESCE(oi.technical_object, '')",
                    "COALESCE(oi.unit, '')",
                    "COALESCE(oi.status, '')",
                ))
                document_search_text = " || ' ' || ".join((
                    "COALESCE(od.document_type, '')",
                    "COALESCE(od.title, '')",
                    "COALESCE(od.filename, '')",
                ))
                alternatives = []
                for keyword in keywords:
                    alternatives.append(
                        f"(search_term_matches({opportunity_search_text}, ?) = 1 "
                        "OR EXISTS (SELECT 1 FROM opportunity_items oi "
                        "WHERE oi.opportunity_id = o.id "
                        f"AND search_term_matches({item_search_text}, ?) = 1) "
                        "OR EXISTS (SELECT 1 FROM opportunity_documents od "
                        "WHERE od.opportunity_id = o.id "
                        f"AND search_term_matches({document_search_text}, ?) = 1))"
                    )
                    params.extend([keyword, keyword, keyword])
                where.append(f"({' OR '.join(alternatives)})")
        object_type = str(filters.get("object_type") or "").lower()
        if object_type in {"material", "servico"}:
            match_column = (
                "object_matches_material"
                if object_type == "material"
                else "object_matches_service"
            )
            where.append(f"o.{match_column} = 1")
        if filters.get("q"):
            query = f"%{filters['q']}%"
            where.append(
                "(o.title LIKE ? OR o.description LIKE ? OR o.buyer_name LIKE ? OR o.process_number LIKE ?)"
            )
            params.extend([query, query, query, query])
        limit = min(max(_integer(filters.get("limit")) or 50, 1), 500)
        offset = max(_integer(filters.get("offset")) or 0, 0)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        use_score_order = score_min is not None or bool(filters.get("sort_by_score"))
        date_field = str(filters.get("date_field") or "closing").strip().lower()
        date_column, date_direction = {
            "publication": ("published_at", "DESC"),
            "opening": ("proposal_start_at", "ASC"),
            "closing": ("proposal_end_at", "ASC"),
        }.get(date_field, ("proposal_end_at", "ASC"))
        date_order = (
            f"CASE WHEN o.{date_column} IS NULL OR o.{date_column} = '' THEN 1 ELSE 0 END, "
            f"o.{date_column} {date_direction}, o.published_at DESC"
        )
        bounded_date_index = None
        object_index_type = (
            "material" if object_type == "material"
            else "service" if object_type == "servico"
            else ""
        )
        bounded_date_filters = {
            "publication": (
                f"idx_opportunities_{object_index_type}_published"
                if object_index_type else "idx_opportunities_published_at",
                filters.get("published_from") or filters.get("published_to"),
            ),
            "opening": (
                f"idx_opportunities_{object_index_type}_proposal_start"
                if object_index_type else "idx_opportunities_proposal_start",
                filters.get("proposal_start_from") or filters.get("proposal_start_to"),
            ),
            "closing": (
                f"idx_opportunities_{object_index_type}_proposal_end"
                if object_index_type else "idx_opportunities_proposal_end",
                proposal_from or proposal_to,
            ),
        }
        candidate_index, has_date_bound = bounded_date_filters.get(
            date_field, (None, None)
        )
        if (
            candidate_index
            and has_date_bound
            and not use_score_order
            and not fts_query
            and date_union_bounds is None
        ):
            bounded_date_index = candidate_index
        bounded_date_order = f"o.{date_column} {date_direction}"
        if date_column != "published_at":
            bounded_date_order += ", o.published_at DESC"
        source_sql = (
            "opportunity_search CROSS JOIN opportunities o "
            "ON o.id = opportunity_search.opportunity_id"
            if fts_query
            else "opportunities o"
        )
        source_params = list(params)
        if date_union_bounds is not None:
            lower_bound, upper_bound = date_union_bounds
            common_conditions = " AND ".join(where)
            common_prefix = f"{common_conditions} AND " if common_conditions else ""
            source_sql = f"""
                (
                    SELECT o.id, o.proposal_start_at, o.proposal_end_at, o.published_at
                    FROM opportunities o
                    INDEXED BY {
                        f'idx_opportunities_{object_index_type}_proposal_end'
                        if object_index_type else 'idx_opportunities_proposal_end'
                    }
                    WHERE {common_prefix}
                      o.proposal_end_at IS NOT NULL AND o.proposal_end_at <> ''
                      AND o.proposal_end_at >= ? AND o.proposal_end_at <= ?
                    UNION ALL
                    SELECT o.id, o.proposal_start_at, o.proposal_end_at, o.published_at
                    FROM opportunities o
                    INDEXED BY {
                        f'idx_opportunities_{object_index_type}_missing_end_published'
                        if object_index_type else 'idx_opportunities_missing_end_published'
                    }
                    WHERE {common_prefix}
                      (o.proposal_end_at IS NULL OR o.proposal_end_at = '')
                      AND o.published_at >= ? AND o.published_at <= ?
                ) o
            """
            source_params = (
                params + [lower_bound, upper_bound]
                + params + [lower_bound, upper_bound]
            )
            clause = ""
        match_map: dict[str, sqlite3.Row] = {}
        item_count_map: dict[str, int] = {}
        window_total: int | None = None
        with self.connect() as connection:
            if use_score_order:
                rows = connection.execute(
                    f"""
                    SELECT o.*, COALESCE(m.score, 0) AS score, m.reasons_json,
                           COUNT(*) OVER() AS filtered_total
                    FROM {source_sql}
                    LEFT JOIN opportunity_matches m
                      ON m.opportunity_id = o.id AND m.company_profile_id = ?
                    {clause}
                    ORDER BY COALESCE(m.score, 0) DESC,
                             {date_order}
                    LIMIT ? OFFSET ?
                    """,
                    [profile_id] + params + [limit, offset],
                ).fetchall()
            else:
                if bounded_date_index is not None:
                    # Keep page and total on one snapshot while steering SQLite to the
                    # date index that already satisfies the requested ordering.
                    connection.execute("BEGIN")
                    page_rows = connection.execute(
                        f"""
                        SELECT o.*
                        FROM opportunities o INDEXED BY {bounded_date_index}
                        {clause}
                        ORDER BY {bounded_date_order}
                        LIMIT ? OFFSET ?
                        """,
                        source_params + [limit, offset],
                    ).fetchall()
                    window_total = int(connection.execute(
                        f"""
                        SELECT COUNT(*)
                        FROM opportunities o INDEXED BY {bounded_date_index}
                        {clause}
                        """,
                        source_params,
                    ).fetchone()[0])
                else:
                    page_rows = connection.execute(
                        f"""
                        SELECT o.*, COUNT(*) OVER() AS filtered_total
                        FROM {source_sql}
                        {clause}
                        ORDER BY {date_order}
                        LIMIT ? OFFSET ?
                        """,
                        source_params + [limit, offset],
                    ).fetchall()
                    window_total = (
                        int(page_rows[0]["filtered_total"]) if page_rows else None
                    )
                if date_union_bounds is not None:
                    page_ids = [row["id"] for row in page_rows]
                    full_rows = connection.execute(
                        f"""
                        SELECT * FROM opportunities
                        WHERE id IN ({','.join('?' for _ in page_ids)})
                        """,
                        page_ids,
                    ).fetchall() if page_ids else []
                    full_map = {row["id"]: row for row in full_rows}
                    rows = [full_map[opportunity_id] for opportunity_id in page_ids]
                else:
                    rows = page_rows
                opportunity_ids = [row["id"] for row in rows]
                if opportunity_ids:
                    matches = connection.execute(
                        f"""
                        SELECT opportunity_id, score, reasons_json
                        FROM opportunity_matches
                        WHERE company_profile_id = ?
                          AND opportunity_id IN ({','.join('?' for _ in opportunity_ids)})
                        """,
                        [profile_id] + opportunity_ids,
                    ).fetchall()
                    match_map = {row["opportunity_id"]: row for row in matches}
            opportunity_ids = [row["id"] for row in rows]
            if opportunity_ids:
                item_counts = connection.execute(
                    f"""
                    SELECT opportunity_id, COUNT(*) AS item_count
                    FROM opportunity_items
                    WHERE opportunity_id IN ({','.join('?' for _ in opportunity_ids)})
                    GROUP BY opportunity_id
                    """,
                    opportunity_ids,
                ).fetchall()
                item_count_map = {
                    row["opportunity_id"]: int(row["item_count"])
                    for row in item_counts
                }
            total = (
                window_total
                if window_total is not None
                else (int(rows[0]["filtered_total"]) if rows else 0)
            )
            if not rows and offset:
                if use_score_order:
                    total = connection.execute(
                        f"""
                        SELECT COUNT(*) FROM opportunities o
                        LEFT JOIN opportunity_matches m
                          ON m.opportunity_id = o.id AND m.company_profile_id = ?
                        {clause}
                        """,
                        [profile_id] + params,
                    ).fetchone()[0]
                else:
                    total = connection.execute(
                        f"SELECT COUNT(*) FROM {source_sql} {clause}",
                        source_params,
                    ).fetchone()[0]
        items = [_row(row) for row in rows]
        for item in items:
            item.pop("filtered_total", None)
            match = match_map.get(item["id"])
            if match is not None:
                item["score"] = match["score"]
                item["reasons"] = _decode_json(match["reasons_json"], [])
            else:
                item["score"] = item.get("score", 0)
                item["reasons"] = _decode_json(item.pop("reasons_json", None), [])
            item["item_count"] = item_count_map.get(item["id"], 0)
            item["items_indexed"] = item["item_count"] > 0
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
            self._refresh_object_classification(connection, opportunity_id, now)
        return len(items)

    def merge_opportunity_items(
        self,
        items_by_opportunity: dict[str, list[OpportunityItem]],
    ) -> dict[str, int]:
        """Upsert item batches without discarding items received on earlier pages."""
        clean_batches = {
            opportunity_id: items
            for opportunity_id, items in items_by_opportunity.items()
            if opportunity_id and items
        }
        if not clean_batches:
            return {"opportunities": 0, "items": 0}

        now = _now()
        item_count = 0
        with self.connect() as connection, connection:
            for opportunity_id, items in clean_batches.items():
                for item in items:
                    connection.execute(
                        """
                        INSERT INTO opportunity_items (
                            id, opportunity_id, source_item_id, lot_number, item_number,
                            title, description, technical_object, quantity, unit,
                            estimated_unit_value, estimated_total_value, currency, status,
                            granularity, confidence, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(opportunity_id, lot_number, item_number) DO UPDATE SET
                            source_item_id = COALESCE(excluded.source_item_id, opportunity_items.source_item_id),
                            title = excluded.title,
                            description = COALESCE(excluded.description, opportunity_items.description),
                            technical_object = COALESCE(
                                excluded.technical_object,
                                opportunity_items.technical_object
                            ),
                            quantity = COALESCE(excluded.quantity, opportunity_items.quantity),
                            unit = COALESCE(excluded.unit, opportunity_items.unit),
                            estimated_unit_value = COALESCE(
                                excluded.estimated_unit_value,
                                opportunity_items.estimated_unit_value
                            ),
                            estimated_total_value = COALESCE(
                                excluded.estimated_total_value,
                                opportunity_items.estimated_total_value
                            ),
                            currency = excluded.currency,
                            status = COALESCE(excluded.status, opportunity_items.status),
                            granularity = excluded.granularity,
                            confidence = MAX(opportunity_items.confidence, excluded.confidence),
                            updated_at = excluded.updated_at
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
                    item_count += 1
                self._refresh_object_classification(connection, opportunity_id, now)
        return {"opportunities": len(clean_batches), "items": item_count}

    def opportunity_has_items(self, opportunity_id: str) -> bool:
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM opportunity_items WHERE opportunity_id = ? LIMIT 1",
                (opportunity_id,),
            ).fetchone() is not None

    def persist_opportunity_items_enrichment(
        self,
        *,
        run_id: str,
        opportunity_id: str,
        items: list[OpportunityItem],
        request_url: str,
        audit_summary: dict[str, Any],
        external_key: str | None = None,
        finish_run: bool = True,
    ) -> dict[str, Any]:
        if not items:
            raise ValueError("cannot persist an empty opportunity item enrichment")

        now = _now()
        raw_json = _json(audit_summary)
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                opportunity = connection.execute(
                    "SELECT id FROM opportunities WHERE id = ?",
                    (opportunity_id,),
                ).fetchone()
                if opportunity is None:
                    raise KeyError(f"opportunity not found: {opportunity_id}")

                existing_count = connection.execute(
                    """
                    SELECT COUNT(*) FROM opportunity_items
                    WHERE opportunity_id = ?
                      AND TRIM(item_number) <> ''
                      AND TRIM(COALESCE(description, title, '')) <> ''
                    """,
                    (opportunity_id,),
                ).fetchone()[0]
                if existing_count:
                    if finish_run:
                        connection.execute(
                            """
                            UPDATE etl_runs SET
                                status = 'success', finished_at = ?, total_fetched = 0,
                                total_inserted = 0, total_updated = 0, total_skipped = 1,
                                total_failed = 0, error_message = NULL, updated_at = ?
                            WHERE id = ?
                            """,
                            (now, now, run_id),
                        )
                    connection.commit()
                    return {"persisted": False, "count": int(existing_count)}

                connection.execute(
                    "DELETE FROM opportunity_items WHERE opportunity_id = ?",
                    (opportunity_id,),
                )
                self._insert_items(connection, opportunity_id, items, now)
                self._refresh_object_classification(connection, opportunity_id, now)
                connection.execute(
                    """
                    INSERT INTO source_records (
                        id, etl_run_id, opportunity_id, source, source_endpoint,
                        request_url, external_key, raw_payload_json, raw_payload_hash,
                        status, captured_at, created_at
                    ) VALUES (?, ?, ?, 'pncp', 'opportunity_item_enrichment',
                              ?, ?, ?, ?, 'success', ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        run_id,
                        opportunity_id,
                        request_url,
                        external_key,
                        raw_json,
                        _hash_text(raw_json),
                        now,
                        now,
                    ),
                )
                if finish_run:
                    connection.execute(
                        """
                        UPDATE etl_runs SET
                            status = 'success', finished_at = ?, total_fetched = ?,
                            total_inserted = ?, total_updated = 0, total_skipped = 0,
                            total_failed = 0, error_message = NULL, updated_at = ?
                        WHERE id = ?
                        """,
                        (now, len(items), len(items), now, run_id),
                    )
                connection.commit()
                return {"persisted": True, "count": len(items)}
            except Exception:
                connection.rollback()
                raise

    def record_opportunity_items_enrichment_failure(
        self,
        *,
        run_id: str,
        opportunity_id: str,
        request_url: str,
        audit_summary: dict[str, Any],
        error_message: str,
        external_key: str | None = None,
    ) -> None:
        now = _now()
        raw_json = _json(audit_summary)
        safe_error = str(error_message or "item enrichment failed")[:2000]
        with self.connect() as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    INSERT INTO source_records (
                        id, etl_run_id, opportunity_id, source, source_endpoint,
                        request_url, external_key, raw_payload_json, raw_payload_hash,
                        status, error_message, captured_at, created_at
                    ) VALUES (?, ?, ?, 'pncp', 'opportunity_item_enrichment',
                              ?, ?, ?, ?, 'failed', ?, ?, ?)
                    """,
                    (
                        uuid.uuid4().hex,
                        run_id,
                        opportunity_id,
                        request_url,
                        external_key,
                        raw_json,
                        _hash_text(raw_json),
                        safe_error,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    UPDATE etl_runs SET
                        status = 'failed', finished_at = ?, total_fetched = 0,
                        total_inserted = 0, total_updated = 0, total_skipped = 0,
                        total_failed = 1, error_message = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (now, safe_error, now, run_id),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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
        ETLRepository._replace_items(
            connection, opportunity_id, opportunity.items, now
        )
        ETLRepository._replace_documents(
            connection, opportunity_id, opportunity.documents, now
        )

    @staticmethod
    def _replace_items(
        connection: sqlite3.Connection,
        opportunity_id: str,
        items: list[OpportunityItem],
        now: str,
    ) -> None:
        connection.execute("DELETE FROM opportunity_items WHERE opportunity_id = ?", (opportunity_id,))
        ETLRepository._insert_items(connection, opportunity_id, items, now)
        ETLRepository._refresh_object_classification(connection, opportunity_id, now)

    @staticmethod
    def _replace_documents(
        connection: sqlite3.Connection,
        opportunity_id: str,
        documents: list[OpportunityDocument],
        now: str,
    ) -> None:
        connection.execute("DELETE FROM opportunity_documents WHERE opportunity_id = ?", (opportunity_id,))
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
    def _refresh_object_classification(
        connection: sqlite3.Connection,
        opportunity_id: str,
        now: str,
    ) -> None:
        opportunity = connection.execute(
            "SELECT title, description FROM opportunities WHERE id = ?",
            (opportunity_id,),
        ).fetchone()
        if opportunity is None:
            return
        opportunity_type = classify_object_text(
            f"{opportunity['title'] or ''} {opportunity['description'] or ''}"
        ) or "unclassified"
        has_material = 0
        has_service = 0
        for item in connection.execute(
            "SELECT title, description FROM opportunity_items WHERE opportunity_id = ?",
            (opportunity_id,),
        ):
            item_type = classify_object_text(
                f"{item['title'] or ''} {item['description'] or ''}"
            )
            has_material = max(has_material, int(item_type == "material"))
            has_service = max(has_service, int(item_type == "servico"))
            if has_material and has_service:
                break
        matches_material = int(
            opportunity_type == "material"
            or has_material
            or (
                opportunity_type == "unclassified"
                and not has_material
                and not has_service
            )
        )
        matches_service = int(
            opportunity_type == "servico"
            or has_service
            or (
                opportunity_type == "unclassified"
                and not has_material
                and not has_service
            )
        )
        connection.execute(
            """
            INSERT INTO opportunity_object_classifications (
                opportunity_id, opportunity_type, has_material, has_service,
                matches_material, matches_service, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(opportunity_id) DO UPDATE SET
                opportunity_type = excluded.opportunity_type,
                has_material = excluded.has_material,
                has_service = excluded.has_service,
                matches_material = excluded.matches_material,
                matches_service = excluded.matches_service,
                updated_at = excluded.updated_at
            """,
            (
                opportunity_id,
                opportunity_type,
                has_material,
                has_service,
                matches_material,
                matches_service,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE opportunities
            SET object_matches_material = ?, object_matches_service = ?, updated_at = ?
            WHERE id = ?
            """,
            (matches_material, matches_service, now, opportunity_id),
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


def _date_lower_bound(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return text


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


def _like_pattern(value: Any) -> str:
    normalized = fold_search_text(value)
    escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


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
