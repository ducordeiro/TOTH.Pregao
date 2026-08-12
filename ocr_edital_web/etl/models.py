"""Small, framework-independent types used by the ETL layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class OpportunityItem:
    source_item_id: str | None
    item_number: str
    title: str
    lot_number: str = ""
    description: str | None = None
    technical_object: str | None = None
    quantity: float | None = None
    unit: str | None = None
    estimated_unit_value: float | None = None
    estimated_total_value: float | None = None
    currency: str = "BRL"
    status: str | None = None
    granularity: str = "item"
    confidence: float = 1.0


@dataclass(slots=True)
class OpportunityDocument:
    document_type: str
    url: str
    title: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    source: str = "pncp"
    download_status: str = "pending"


@dataclass(slots=True)
class NormalizedOpportunity:
    external_key: str
    source: str
    title: str
    pncp_control_number: str | None = None
    source_cnpj: str | None = None
    year: int | None = None
    sequence: int | None = None
    process_number: str | None = None
    description: str | None = None
    buyer_name: str | None = None
    buyer_cnpj: str | None = None
    uf: str | None = None
    city: str | None = None
    uasg: str | None = None
    modality: str | None = None
    modality_code: int | None = None
    status: str | None = None
    estimated_value: float | None = None
    currency: str = "BRL"
    published_at: str | None = None
    proposal_start_at: str | None = None
    proposal_end_at: str | None = None
    source_url: str | None = None
    detail_url: str | None = None
    origin_url: str | None = None
    items: list[OpportunityItem] = field(default_factory=list)
    documents: list[OpportunityDocument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MatchResult:
    company_profile_id: str = "default"
    score: float = 0.0
    matched_keywords: list[str] = field(default_factory=list)
    matched_items: list[str] = field(default_factory=list)
    matched_regions: list[str] = field(default_factory=list)
    matched_modalities: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PageResult:
    records: list[dict[str, Any]]
    page_number: int
    total_pages: int | None
    request_url: str
    raw_payload: Any


@dataclass(slots=True)
class FetchedPayload:
    payload: Any
    request_url: str
