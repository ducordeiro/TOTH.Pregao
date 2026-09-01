"""ETL orchestration with bounded, auditable synchronization runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable

from .classifier import OpportunityClassifier
from .models import FetchedPayload, PageResult
from .repository import ETLRepository


@dataclass(slots=True)
class SyncRequest:
    endpoint: str
    filters: dict[str, Any] = field(default_factory=dict)
    run_type: str = "manual"
    dry_run: bool = False
    max_pages: int | None = 1
    max_records: int | None = 100
    fetch_details: bool = True
    item_max_pages: int | None = 20
    company_profile: dict[str, Any] = field(default_factory=dict)
    page_completed: Callable[[PageResult], None] | None = field(
        default=None, repr=False
    )


class ETLSyncService:
    def __init__(
        self,
        repository: ETLRepository,
        connector: Any,
        mapper: Any,
        classifier: OpportunityClassifier | None = None,
    ) -> None:
        self.repository = repository
        self.connector = connector
        self.mapper = mapper
        self.classifier = classifier or OpportunityClassifier()

    def sync(self, request: SyncRequest) -> dict[str, Any]:
        _validate_limits(request)
        queries = self._build_queries(request.endpoint, request.filters)
        self.repository.initialize()
        source = str(getattr(self.connector, "SOURCE", getattr(self.mapper, "source", "unknown")))
        run_filters = {
            "queries": queries,
            "dry_run": request.dry_run,
            "max_pages": request.max_pages,
            "max_records": request.max_records,
            "fetch_details": request.fetch_details,
        }
        run_id = self.repository.create_run(source, request.run_type, run_filters)
        counters = {"fetched": 0, "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}
        try:
            stop = False
            for query in queries:
                pages = self.connector.iter_endpoint(request.endpoint, query, request.max_pages)
                for page in pages:
                    page_fully_processed = True
                    for raw_record in page.records:
                        if request.max_records is not None and counters["fetched"] >= request.max_records:
                            stop = True
                            page_fully_processed = False
                            break
                        counters["fetched"] += 1
                        self._process_record(request, run_id, source, page, raw_record, counters)
                    if page_fully_processed and request.page_completed is not None:
                        request.page_completed(page)
                    if stop:
                        break
                if stop:
                    break
        except Exception as exc:
            self.repository.finish_run(
                run_id,
                status="failed",
                counters=counters,
                error_message=str(exc),
            )
            raise
        status = "dry_run" if request.dry_run else ("partial" if counters["failed"] else "success")
        self.repository.finish_run(run_id, status=status, counters=counters)
        return {"run_id": run_id, "status": status, **counters}

    def _process_record(
        self,
        request: SyncRequest,
        run_id: str,
        source: str,
        page: PageResult,
        raw_record: dict[str, Any],
        counters: dict[str, int],
    ) -> None:
        raw_composite: dict[str, Any] = {
            "listing": raw_record,
            "detail": None,
            "items": [],
            "documents": [],
            "enrichment_errors": [],
        }
        try:
            detail, items, documents = self._enrich(request, raw_record, raw_composite)
            opportunity = self.mapper.map(
                raw_record,
                detail=detail,
                items=items if items is not None else None,
                documents=documents if documents is not None else None,
            )
            match = self.classifier.classify(opportunity, request.company_profile)
            if request.dry_run:
                outcome = self.repository.preview_upsert(opportunity)
            else:
                outcome, _ = self.repository.persist_record(
                    run_id=run_id,
                    source_endpoint=request.endpoint,
                    request_url=page.request_url,
                    raw_payload=raw_composite,
                    opportunity=opportunity,
                    match=match,
                    replace_children=False,
                    replace_items=_has_item_payload(raw_record, items),
                    replace_documents=_has_document_payload(raw_record, documents),
                )
            counters[outcome] += 1
        except Exception as exc:
            counters["failed"] += 1
            if not request.dry_run:
                self.repository.save_failed_source_record(
                    run_id=run_id,
                    source=source,
                    source_endpoint=request.endpoint,
                    request_url=page.request_url,
                    raw_payload=raw_composite,
                    error_message=str(exc),
                )

    def _enrich(
        self,
        request: SyncRequest,
        raw_record: dict[str, Any],
        raw_composite: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
        if not request.fetch_details or not hasattr(self.mapper, "identify"):
            return None, None, None
        cnpj, year, sequence = self.mapper.identify(raw_record)
        if not (cnpj and year is not None and sequence is not None):
            return None, None, None

        detail: dict[str, Any] | None = None
        items: list[dict[str, Any]] | None = None
        documents: list[dict[str, Any]] | None = None
        if hasattr(self.connector, "fetch_detail"):
            try:
                fetched: FetchedPayload = self.connector.fetch_detail(cnpj, year, sequence)
                if isinstance(fetched.payload, dict):
                    detail = fetched.payload
                raw_composite["detail"] = fetched.payload
                raw_composite["detail_request_url"] = fetched.request_url
            except Exception as exc:
                raw_composite["enrichment_errors"].append(f"detail: {exc}")
        if hasattr(self.connector, "iter_items"):
            try:
                items = []
                item_pages = []
                for item_page in self.connector.iter_items(
                    cnpj, year, sequence, request.item_max_pages
                ):
                    items.extend(item_page.records)
                    item_pages.append(item_page.raw_payload)
                raw_composite["items"] = item_pages
                if not items:
                    raw_composite["enrichment_errors"].append(
                        "items: source returned no items"
                    )
                    items = None
            except Exception as exc:
                raw_composite["enrichment_errors"].append(f"items: {exc}")
                items = None
        if hasattr(self.connector, "fetch_documents"):
            try:
                fetched = self.connector.fetch_documents(cnpj, year, sequence)
                documents = _extract_records(fetched.payload)
                raw_composite["documents"] = fetched.payload
                raw_composite["documents_request_url"] = fetched.request_url
            except Exception as exc:
                raw_composite["enrichment_errors"].append(f"documents: {exc}")
        return detail, items, documents

    def _build_queries(self, endpoint: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        clean = {key: value for key, value in filters.items() if value is not None and value != ""}
        _apply_date_alias(clean, "dataInicial", "date_from", "start_date", "published_from")
        _apply_date_alias(clean, "dataFinal", "date_to", "end_date", "published_to")
        for key in ("dataInicial", "dataFinal"):
            if key in clean:
                clean[key] = _pncp_date(clean[key], key)

        source = str(getattr(self.connector, "SOURCE", ""))
        if source != "pncp":
            return [clean]
        if endpoint not in {"publicacao", "atualizacao", "proposta"}:
            raise ValueError(f"unsupported PNCP sync endpoint: {endpoint}")
        if endpoint in {"publicacao", "atualizacao"}:
            missing_dates = [key for key in ("dataInicial", "dataFinal") if not clean.get(key)]
            if missing_dates:
                raise ValueError(f"{endpoint} requires {', '.join(missing_dates)}")
        if endpoint == "proposta" and not clean.get("dataFinal"):
            raise ValueError("proposta requires dataFinal")

        modalities = clean.pop("modality_codes", None)
        direct_modality = clean.get("codigoModalidadeContratacao")
        if endpoint in {"publicacao", "atualizacao"} and direct_modality is None and not modalities:
            raise ValueError(f"{endpoint} requires codigoModalidadeContratacao or modality_codes")
        if direct_modality is not None:
            modalities = direct_modality if isinstance(direct_modality, (list, tuple, set)) else [direct_modality]
        if modalities:
            clean.pop("codigoModalidadeContratacao", None)
            queries = []
            for modality in modalities:
                query = dict(clean)
                query["codigoModalidadeContratacao"] = int(modality)
                queries.append(query)
            return queries
        return [clean]


def _validate_limits(request: SyncRequest) -> None:
    if request.max_pages is not None and request.max_pages <= 0:
        raise ValueError("max_pages must be greater than zero")
    if request.max_records is not None and request.max_records <= 0:
        raise ValueError("max_records must be greater than zero")
    if request.item_max_pages is not None and request.item_max_pages <= 0:
        raise ValueError("item_max_pages must be greater than zero")


def _apply_date_alias(target: dict[str, Any], destination: str, *aliases: str) -> None:
    if destination in target:
        return
    for alias in aliases:
        if alias in target:
            target[destination] = target.pop(alias)
            return


def _pncp_date(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        try:
            datetime.strptime(text, "%Y%m%d")
            return text
        except ValueError as exc:
            raise ValueError(f"{field_name} is not a valid YYYYMMDD date") from exc
    try:
        parsed = date.fromisoformat(text[:10])
        return parsed.strftime("%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"{field_name} must use YYYYMMDD or YYYY-MM-DD") from exc


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [value for value in payload if isinstance(value, dict)]
    if isinstance(payload, dict):
        for key in ("data", "items", "content", "results", "resultado"):
            if key in payload:
                result = _extract_records(payload[key])
                if result:
                    return result
    return []


def _has_item_payload(
    raw_record: dict[str, Any],
    items: list[dict[str, Any]] | None,
) -> bool:
    if items is not None:
        return True
    return any(
        key in raw_record
        for key in (
            "itens",
            "items",
            "listaItens",
        )
    )


def _has_document_payload(
    raw_record: dict[str, Any],
    documents: list[dict[str, Any]] | None,
) -> bool:
    if documents is not None:
        return True
    return any(
        key in raw_record
        for key in (
            "documentos",
            "arquivos",
            "anexos",
        )
    )
