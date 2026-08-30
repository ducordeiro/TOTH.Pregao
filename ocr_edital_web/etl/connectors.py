"""HTTP connectors for PNCP and Compras.gov open-data sources."""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping
from typing import Any

from .models import FetchedPayload, PageResult


class ConnectorError(RuntimeError):
    """Raised when a source cannot be read after the configured retries."""


class _RateLimitResponse(RuntimeError):
    pass


class HttpJsonClient:
    def __init__(
        self,
        timeout: float = 20.0,
        retries: int = 2,
        retry_backoff: float = 0.5,
        user_agent: str = "TOTH-ETL/1.0 (+https://pncp.gov.br)",
        opener: Any | None = None,
        sleeper: Any = time.sleep,
        request_delay: float = 0.0,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if retries < 0:
            raise ValueError("retries cannot be negative")
        if request_delay < 0:
            raise ValueError("request_delay cannot be negative")
        self.timeout = timeout
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.user_agent = user_agent
        self.opener = opener or urllib.request.urlopen
        self.sleeper = sleeper
        self.request_delay = request_delay

    def get(self, url: str, params: Mapping[str, Any] | None = None) -> FetchedPayload:
        request_url = _url_with_query(url, params)
        request = urllib.request.Request(
            request_url,
            headers={"Accept": "application/json", "User-Agent": self.user_agent},
            method="GET",
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                if self.request_delay:
                    self.sleeper(self.request_delay)
                with self.opener(request, timeout=self.timeout) as response:
                    if getattr(response, "status", None) == 204:
                        return FetchedPayload(payload={"data": []}, request_url=request_url)
                    charset = response.headers.get_content_charset() or "utf-8"
                    response_text = response.read().decode(charset)
                    try:
                        payload = json.loads(response_text)
                    except json.JSONDecodeError as exc:
                        lowered = response_text.casefold()
                        stripped = response_text.lstrip()
                        if (
                            not stripped
                            or stripped.startswith("<")
                            or "limite de requisi" in lowered
                            or "too many requests" in lowered
                        ):
                            raise _RateLimitResponse(
                                "HTTP 429: resposta temporaria nao JSON do PNCP"
                            ) from exc
                        raise
                    return FetchedPayload(payload=payload, request_url=request_url)
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code < 500 and exc.code != 429:
                    break
            except (
                urllib.error.URLError,
                TimeoutError,
                socket.timeout,
                json.JSONDecodeError,
                _RateLimitResponse,
            ) as exc:
                last_error = exc
            if attempt < self.retries:
                self.sleeper(self.retry_backoff * (2**attempt))
        raise ConnectorError(f"GET {request_url} failed: {last_error}") from last_error


class PNCPConnector:
    SOURCE = "pncp"
    ENDPOINTS = {
        "publicacao": "/v1/contratacoes/publicacao",
        "atualizacao": "/v1/contratacoes/atualizacao",
        "proposta": "/v1/contratacoes/proposta",
    }

    def __init__(
        self,
        base_url: str = "https://pncp.gov.br/api/consulta",
        integration_base_url: str = "https://pncp.gov.br/api/pncp",
        client: HttpJsonClient | None = None,
        page_size: int = 50,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.integration_base_url = integration_base_url.rstrip("/")
        self.client = client or HttpJsonClient()
        self.page_size = page_size

    def iter_publications(self, filters: Mapping[str, Any], max_pages: int | None = None) -> Iterator[PageResult]:
        return self.iter_endpoint("publicacao", filters, max_pages)

    def iter_updates(self, filters: Mapping[str, Any], max_pages: int | None = None) -> Iterator[PageResult]:
        return self.iter_endpoint("atualizacao", filters, max_pages)

    def iter_open_proposals(self, filters: Mapping[str, Any], max_pages: int | None = None) -> Iterator[PageResult]:
        return self.iter_endpoint("proposta", filters, max_pages)

    def iter_endpoint(
        self,
        endpoint: str,
        filters: Mapping[str, Any],
        max_pages: int | None = None,
    ) -> Iterator[PageResult]:
        if endpoint not in self.ENDPOINTS:
            raise ValueError(f"unsupported PNCP endpoint: {endpoint}")
        yield from self._iter_pages(
            f"{self.base_url}{self.ENDPOINTS[endpoint]}", filters, max_pages
        )

    def fetch_detail(self, cnpj: str, year: int, sequence: int) -> FetchedPayload:
        path = f"/v1/orgaos/{_digits(cnpj)}/compras/{int(year)}/{int(sequence)}"
        return self.client.get(f"{self.base_url}{path}")

    def iter_items(
        self,
        cnpj: str,
        year: int,
        sequence: int,
        max_pages: int | None = None,
    ) -> Iterator[PageResult]:
        path = f"/v1/orgaos/{_digits(cnpj)}/compras/{int(year)}/{int(sequence)}/itens"
        yield from self._iter_pages(
            f"{self.integration_base_url}{path}", {}, max_pages
        )

    def fetch_documents(self, cnpj: str, year: int, sequence: int) -> FetchedPayload:
        path = f"/v1/orgaos/{_digits(cnpj)}/compras/{int(year)}/{int(sequence)}/arquivos"
        return self.client.get(f"{self.integration_base_url}{path}")

    def _iter_pages(
        self,
        url: str,
        filters: Mapping[str, Any],
        max_pages: int | None,
    ) -> Iterator[PageResult]:
        if max_pages is not None and max_pages <= 0:
            return
        page = max(1, _to_int(filters.get("pagina")) or 1)
        emitted = 0
        while max_pages is None or emitted < max_pages:
            params = dict(filters)
            params["pagina"] = page
            params.setdefault("tamanhoPagina", self.page_size)
            fetched = self.client.get(url, params)
            records = _extract_records(fetched.payload)
            total_pages = _extract_total_pages(fetched.payload)
            yield PageResult(records, page, total_pages, fetched.request_url, fetched.payload)
            emitted += 1
            if (
                not records
                or len(records) < int(params["tamanhoPagina"])
                or (total_pages is not None and page >= total_pages)
            ):
                break
            page += 1


class ComprasGovConnector:
    """Configurable connector because the open-data resource may change by module."""

    SOURCE = "comprasgov"

    def __init__(
        self,
        base_url: str = "https://dadosabertos.compras.gov.br",
        resource_path: str = "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
        client: HttpJsonClient | None = None,
        page_size: int = 50,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.resource_path = resource_path
        self.client = client or HttpJsonClient()
        self.page_size = page_size

    def iter_endpoint(
        self,
        endpoint: str,
        filters: Mapping[str, Any],
        max_pages: int | None = None,
    ) -> Iterator[PageResult]:
        path = endpoint if endpoint.startswith("/") else self.resource_path
        url = path if path.startswith("http://") or path.startswith("https://") else f"{self.base_url}{path}"
        if max_pages is not None and max_pages <= 0:
            return
        page = max(1, _to_int(filters.get("pagina")) or 1)
        emitted = 0
        while max_pages is None or emitted < max_pages:
            params = dict(filters)
            params["pagina"] = page
            params.setdefault("tamanhoPagina", self.page_size)
            fetched = self.client.get(url, params)
            records = _extract_records(fetched.payload)
            total_pages = _extract_total_pages(fetched.payload)
            yield PageResult(records, page, total_pages, fetched.request_url, fetched.payload)
            emitted += 1
            if (
                not records
                or len(records) < int(params["tamanhoPagina"])
                or (total_pages is not None and page >= total_pages)
            ):
                break
            page += 1


def _url_with_query(url: str, params: Mapping[str, Any] | None) -> str:
    if not params:
        return url
    clean = {key: value for key, value in params.items() if value is not None and value != ""}
    query = urllib.parse.urlencode(clean, doseq=True)
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query}" if query else url


def _extract_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("data", "items", "content", "results", "resultado"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_records(value)
            if nested:
                return nested
    return []


def _extract_total_pages(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in ("totalPaginas", "totalPages", "total_pages", "quantidadePaginas"):
        value = _to_int(payload.get(key))
        if value is not None:
            return value
    page_data = payload.get("page") or payload.get("paginacao")
    if isinstance(page_data, dict):
        return _extract_total_pages(page_data)
    return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())
