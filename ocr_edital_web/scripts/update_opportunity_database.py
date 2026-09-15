"""Resumable publication queue, alongside the existing item/index pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import fields
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.connectors import ConnectorError, PNCPConnector
from etl.mappers import PNCPMapper
from etl.preferred_source import ComprasGovSource, PreferredProcurementConnector
from etl.repository import ETLRepository
from etl.service import ETLSyncService, SyncRequest
from scripts.enrich_missing_pncp_items import (
    PacedHttpJsonClient, RequestPacer, _exclusive_process, _write_status,
)

STATE = ROOT / "data/publication_update.status.json"


class InitializedRepository(ETLRepository):
    last_run_id = None

    def create_run(self, *args, **kwargs):
        self.last_run_id = super().create_run(*args, **kwargs)
        return self.last_run_id

    def initialize(self):
        if not getattr(self, "initialized", False):
            super().initialize()
            self.initialized = True


class PreservingPublicationMapper(PNCPMapper):
    def __init__(self, repository):
        self.repository = repository

    def map(self, *args, **kwargs):
        opportunity = super().map(*args, **kwargs)
        with self.repository.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM opportunities WHERE external_key=?", (opportunity.external_key,),
            ).fetchone()
        if existing:
            for field in fields(opportunity):
                if field.name in existing.keys() and getattr(opportunity, field.name) in (None, ""):
                    setattr(opportunity, field.name, existing[field.name])
        return opportunity


class CheckedPublications:
    SOURCE = "pncp"

    def __init__(self, connector, on_page=None):
        self.connector = connector
        self.on_page = on_page or (lambda page: None)

    def iter_endpoint(self, endpoint, filters, max_pages=None):
        seen = set()
        received = 0
        expected = None
        last = None
        for page in self.connector.iter_endpoint(endpoint, filters, max_pages):
            payload = page.raw_payload
            if isinstance(payload, dict) and isinstance(payload.get("totalRegistros"), int):
                total = payload["totalRegistros"]
                if expected is not None and total != expected:
                    raise ConnectorError("Total mudou durante a consulta; unidade permanece pendente")
                expected = total
            raw_rows = payload.get("data", payload.get("resultado", page.records)) if isinstance(payload, dict) else page.records
            received += len(raw_rows)
            for row in page.records:
                key = row.get("numeroControlePNCP")
                if not key or key in seen:
                    raise ConnectorError("Identidade ausente ou repetida na paginacao")
                seen.add(key)
            self.on_page(page)
            last = page
            yield page
        if last is None:
            raise ConnectorError("Fonte nao retornou pagina verificavel")
        if expected is not None and received != expected:
            raise ConnectorError(f"Paginacao incompleta: {received} de {expected}")
        if last.total_pages and last.page_number < last.total_pages:
            raise ConnectorError("Paginacao terminou antes da ultima pagina")


def pending_units(start, end, completed):
    units = []
    day = end
    while day >= start:
        for modality in range(1, 20):
            key = f"{day.isoformat()}:{modality}"
            if key not in completed:
                units.append((key, day.isoformat(), modality))
        day -= timedelta(days=1)
    return units


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date-from", default="2026-06-01")
    parser.add_argument("--date-to", default=date.today().isoformat())
    parser.add_argument("--database", default=str(ROOT / "data/pncp.sqlite3"))
    parser.add_argument("--state", default=str(STATE))
    parser.add_argument("--limit-units", type=int)
    args = parser.parse_args()
    start, end = date.fromisoformat(args.date_from), date.fromisoformat(args.date_to)
    if start > end or (args.limit_units is not None and args.limit_units < 1):
        parser.error("Periodo ou limite invalido")
    state_path = Path(args.state)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    with _exclusive_process(state_path.with_suffix(".pid")):
        database = str(Path(args.database).resolve())
        old = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        if old and old.get("database") != database:
            raise ValueError("Arquivo de progresso pertence a outro banco")
        completed = dict(old.get("completed_units", {}))
        units = pending_units(start, end, completed)
        state = {"pid": os.getpid(), "database": database, "status": "initializing",
                 "date_from": start.isoformat(), "date_to": end.isoformat(),
                 "started_at": datetime.now().astimezone().isoformat(), "updated_at": None,
                 "provider_priority": ["comprasgov", "pncp"], "order": "newest_first",
                 "total_units": (end - start).days * 19 + 19, "pending_at_start": len(units),
                 "completed_units": completed, "failed_units": {}, "current_unit": None,
                 "attempted_units": 0, "pages_received": 0,
                 "counters": dict.fromkeys(("fetched", "inserted", "updated", "skipped", "failed"), 0)}
        began = time.monotonic()

        def save():
            state["updated_at"] = datetime.now().astimezone().isoformat()
            state["remaining_units"] = len(pending_units(start, end, completed))
            elapsed = time.monotonic() - began
            attempted = state["attempted_units"]
            state["estimated_seconds_first_pass"] = (
                round(elapsed / attempted * max(0, len(units) - attempted)) if attempted >= 10 else None
            )
            _write_status(state_path, state)

        save()
        repository = InitializedRepository(database)
        repository.initialize()
        def client():
            return PacedHttpJsonClient(pacer=RequestPacer(3), timeout=12, retries=1, retry_backoff=2)
        preferred = PreferredProcurementConnector(
            primary=ComprasGovSource(client=client()), fallback=PNCPConnector(client=client()),
        )
        def on_page(page):
            state["pages_received"] += 1
            state["last_source_url"] = page.request_url
            state["last_page"] = page.page_number
            state["source_pages"] = page.total_pages
            save()
        service = ETLSyncService(repository, CheckedPublications(preferred, on_page), PreservingPublicationMapper(repository))
        state["status"] = "running"
        for key, day, modality in units[:args.limit_units]:
            state["current_unit"] = {"date": day, "modality": modality}
            repository.last_run_id = None
            save()
            try:
                result = service.sync(SyncRequest(
                    endpoint="publicacao", filters={"date_from": day, "date_to": day, "modality_codes": [modality]},
                    run_type="publication_update", max_pages=None, max_records=None, fetch_details=False,
                ))
                for counter in state["counters"]:
                    state["counters"][counter] += result[counter]
                if result["status"] == "success":
                    completed[key] = {"run_id": result["run_id"], "finished_at": datetime.now().astimezone().isoformat()}
                else:
                    state["failed_units"][key] = result
            except Exception as exc:
                state["failed_units"][key] = {"error": str(exc)}
                if repository.last_run_id:
                    with repository.connect() as connection:
                        failed_run = connection.execute("SELECT * FROM etl_runs WHERE id=?", (repository.last_run_id,)).fetchone()
                    for counter in state["counters"]:
                        state["counters"][counter] += int(failed_run[f"total_{counter}"] or 0)
                    state["failed_units"][key]["run_id"] = repository.last_run_id
                logging.exception("Unidade pendente: %s", key)
            state["attempted_units"] += 1
            save()
            print(json.dumps({"unit": key, "remaining": state["remaining_units"], "counters": state["counters"]}), flush=True)
        state["status"] = "completed" if not state["remaining_units"] else "partial"
        state["current_unit"] = None
        save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
