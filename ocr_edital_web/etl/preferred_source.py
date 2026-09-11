"""Compras.gov first, with PNCP fallback at each supported resource boundary."""

import logging
import re
import threading
import time

from .connectors import ConnectorError, HttpJsonClient, PNCPConnector
from .models import FetchedPayload, PageResult

LOGGER = logging.getLogger("toth.pregao.sources")
BASE = "https://dadosabertos.compras.gov.br"
PURCHASES = "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133"
DETAIL = "/modulo-contratacoes/1.1_consultarContratacoes_PNCP_14133_Id"
ITEMS = "/modulo-contratacoes/2.1_consultarItensContratacoes_PNCP_14133_Id"
# Verified against records exposing both codigoModalidade and modalidadeIdPncp.
# Unknown equivalences deliberately use PNCP instead of guessing.
MODALITIES = {6: 5, 8: 6}


def control_number(cnpj, year, sequence):
    return f"{cnpj}-1-{int(sequence):06d}/{int(year)}"


def canonical_purchase(record):
    row = dict(record)
    for target, source in {
        "anoCompra": "anoCompraPncp", "sequencialCompra": "sequencialCompraPncp",
        "modalidadeId": "modalidadeIdPncp", "situacaoCompraNome": "situacaoCompraNomePncp",
        "dataAberturaProposta": "dataAberturaPropostaPncp",
        "dataEncerramentoProposta": "dataEncerramentoPropostaPncp",
        "modoDisputaNome": "modoDisputaNomePncp",
    }.items():
        if row.get(target) is None:
            row[target] = row.get(source)
    row["orgaoEntidade"] = {"cnpj": row.get("orgaoEntidadeCnpj"), "razaoSocial": row.get("orgaoEntidadeRazaoSocial")}
    row["unidadeOrgao"] = {
        "codigoUnidade": row.get("unidadeOrgaoCodigoUnidade"),
        "nomeUnidade": row.get("unidadeOrgaoNomeUnidade"),
        "ufSigla": row.get("unidadeOrgaoUfSigla"),
        "municipioNome": row.get("unidadeOrgaoMunicipioNome"),
    }
    return row


def canonical_item(record):
    row = dict(record)
    row["numeroItem"] = row.get("numeroItemPncp") or row.get("numeroItemCompra")
    detailed = str(row.get("descricaodetalhada") or "").strip()
    short = str(row.get("descricaoResumida") or "").strip()
    row["descricao"] = detailed or short
    if detailed and short and short.casefold() not in detailed.casefold():
        row["descricao"] = f"{short} - {detailed}"
    if not row["numeroItem"] or not row["descricao"]:
        raise ConnectorError("Compras.gov: item sem numero ou descricao")
    if row.get("numeroGrupo") in (0, "0"):
        row["numeroGrupo"] = ""
    return row


class ComprasGovSource:
    # A failing endpoint must not delay every detail request in a batch.
    _cooldowns = {}
    _lock = threading.Lock()

    def __init__(self, client=None):
        self.client = client or HttpJsonClient(timeout=4, retries=0)

    def request(self, endpoint, params):
        with self._lock:
            if self._cooldowns.get(endpoint, 0) > time.monotonic():
                raise ConnectorError(f"Compras.gov: endpoint em espera temporaria: {endpoint}")
        try:
            fetched = self.client.get(BASE + endpoint, params)
            payload = fetched.payload
            if not isinstance(payload, dict) or not isinstance(payload.get("resultado"), list):
                raise ConnectorError("Compras.gov: formato de resposta invalido")
            if any(not isinstance(row, dict) for row in payload["resultado"]):
                raise ConnectorError("Compras.gov: registro invalido")
            for key in ("totalRegistros", "totalPaginas", "paginasRestantes"):
                if not isinstance(payload.get(key), int) or payload[key] < 0:
                    raise ConnectorError(f"Compras.gov: paginacao invalida ({key})")
            return fetched
        except Exception:
            with self._lock:
                self._cooldowns[endpoint] = time.monotonic() + 30
            raise

    def by_identity(self, endpoint, cnpj, year, sequence):
        control = control_number(cnpj, year, sequence)
        fetched = self.request(endpoint, {"tipo": "numeroControlePNCPCompra", "codigo": control})
        payload = fetched.payload
        records = payload["resultado"]
        if not records or payload["paginasRestantes"] or len(records) != payload["totalRegistros"]:
            raise ConnectorError("Compras.gov: resposta vazia ou incompleta")
        for row in records:
            identity = row.get("numeroControlePNCPCompra") if endpoint == ITEMS else row.get("numeroControlePNCP")
            if identity != control:
                raise ConnectorError("Compras.gov: resposta pertence a outra contratacao")
        return fetched

    def fetch_detail(self, cnpj, year, sequence):
        fetched = self.by_identity(DETAIL, cnpj, year, sequence)
        if len(fetched.payload["resultado"]) != 1:
            raise ConnectorError("Compras.gov: identificacao ambigua")
        row = canonical_purchase(fetched.payload["resultado"][0])
        if (str(row.get("orgaoEntidadeCnpj")), row.get("anoCompra"), row.get("sequencialCompra")) != (str(cnpj), int(year), int(sequence)):
            raise ConnectorError("Compras.gov: campos de identificacao divergentes")
        if not row.get("objetoCompra") or row.get("contratacaoExcluida"):
            raise ConnectorError("Compras.gov: contratacao indisponivel")
        return FetchedPayload(row, fetched.request_url)

    def fetch_items(self, cnpj, year, sequence):
        fetched = self.by_identity(ITEMS, cnpj, year, sequence)
        rows = [canonical_item(row) for row in fetched.payload["resultado"]]
        keys = [(str(row.get("numeroGrupo") or ""), str(row["numeroItem"])) for row in rows]
        if len(set(keys)) != len(keys):
            raise ConnectorError("Compras.gov: itens duplicados")
        return PageResult(rows, 1, 1, fetched.request_url, fetched.payload)

    def iter_publications(self, filters, max_pages=20):
        seen = set()
        expected = None
        received = 0
        for page in range(1, max_pages + 1):
            fetched = self.request(PURCHASES, {**filters, "pagina": page, "tamanhoPagina": 500})
            payload = fetched.payload
            records = payload["resultado"]
            if expected is None:
                expected = payload["totalRegistros"]
            if expected != payload["totalRegistros"]:
                raise ConnectorError("Compras.gov: total alterado durante a paginacao")
            for row in records:
                key = row.get("numeroControlePNCP")
                if not re.fullmatch(r"\d{14}-1-\d+/\d{4}", str(key or "")) or key in seen:
                    raise ConnectorError("Compras.gov: identidade invalida ou pagina repetida")
                seen.add(key)
            received += len(records)
            yield PageResult([canonical_purchase(row) for row in records], page,
                             payload["totalPaginas"], fetched.request_url, payload)
            if not payload["paginasRestantes"]:
                if received != expected:
                    raise ConnectorError("Compras.gov: contagem incompleta")
                return
            if not records:
                raise ConnectorError("Compras.gov: pagina vazia antes do fim")
        raise ConnectorError("Compras.gov: limite de paginas atingido; consulta incompleta")


class PreferredProcurementConnector:
    # PNCP business identity is retained; request_url records the actual provider.
    SOURCE = "pncp"

    def __init__(self, *args, primary=None, fallback=None, **kwargs):
        self.primary = primary or ComprasGovSource()
        self.fallback = fallback or PNCPConnector(*args, **kwargs)

    def fetch_detail(self, cnpj, year, sequence):
        try:
            return self.primary.fetch_detail(cnpj, year, sequence)
        except Exception as exc:
            LOGGER.info("Compras.gov detalhe -> PNCP: %s", exc)
            return self.fallback.fetch_detail(cnpj, year, sequence)

    def iter_items(self, cnpj, year, sequence, max_pages=None):
        if max_pages is not None and max_pages <= 0:
            return
        try:
            page = self.primary.fetch_items(cnpj, year, sequence)
        except Exception as exc:
            LOGGER.info("Compras.gov itens -> PNCP: %s", exc)
            yield from self.fallback.iter_items(cnpj, year, sequence, max_pages)
        else:
            yield page

    def fetch_documents(self, cnpj, year, sequence):
        # The documented Compras.gov module has no attachment resource.
        return self.fallback.fetch_documents(cnpj, year, sequence)

    def iter_endpoint(self, endpoint, filters, max_pages=None):
        # Only publication dates have an equivalent filter in Compras.gov.
        if endpoint == "publicacao":
            try:
                def iso(value):
                    text = str(value)
                    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 else text
                query = {
                    "dataPublicacaoPncpInicial": iso(filters["dataInicial"]),
                    "dataPublicacaoPncpFinal": iso(filters["dataFinal"]),
                    "codigoModalidade": MODALITIES[int(filters["codigoModalidadeContratacao"])],
                    "unidadeOrgaoUfSigla": filters.get("uf"),
                    "orgaoEntidadeCnpj": filters.get("cnpj"),
                    "unidadeOrgaoCodigoUnidade": filters.get("codigoUnidadeAdministrativa"),
                    "unidadeOrgaoCodigoIbge": filters.get("codigoMunicipioIbge"),
                }
                if filters.get("idUsuario") or int(filters.get("pagina") or 1) != 1:
                    raise ConnectorError("Compras.gov: filtro sem equivalencia")
                pages = list(self.primary.iter_publications(query, max_pages or 20))
                for page in pages:
                    page.records[:] = [row for row in page.records
                                       if row.get("modalidadeId") == int(filters["codigoModalidadeContratacao"])]
                if not any(page.records for page in pages):
                    raise ConnectorError("Compras.gov: nenhuma contratacao retornada")
            except Exception as exc:
                LOGGER.info("Compras.gov publicacao -> PNCP: %s", exc)
            else:
                yield from pages
                return
        yield from self.fallback.iter_endpoint(endpoint, filters, max_pages)
