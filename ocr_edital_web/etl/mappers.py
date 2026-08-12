"""Map source-specific payloads into the internal opportunity model."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from .models import NormalizedOpportunity, OpportunityDocument, OpportunityItem


class MappingError(ValueError):
    """Raised when a source record has no stable business identity."""


class PNCPMapper:
    source = "pncp"

    def map(
        self,
        payload: dict[str, Any],
        *,
        detail: dict[str, Any] | None = None,
        items: list[dict[str, Any]] | None = None,
        documents: list[dict[str, Any]] | None = None,
    ) -> NormalizedOpportunity:
        record = _deep_merge(payload, detail or {})
        cnpj = _digits(_first(
            record,
            "numeroCnpj",
            "cnpj",
            "orgao_cnpj",
            "orgaoEntidade.cnpj",
            "orgaoEntidadeCnpj",
        )) or None
        year = _integer(_first(record, "anoCompra", "anoCompraPncp", "ano", "ano_compra"))
        sequence = _integer(
            _first(
                record,
                "sequencialCompra",
                "sequencialCompraPncp",
                "numeroSequencial",
                "numero_sequencial",
                "sequencial",
            )
        )
        control = _text(
            _first(record, "numeroControlePNCP", "numeroControlePncp", "numero_controle_pncp")
        )
        if not control:
            if not (cnpj and year is not None and sequence is not None):
                raise MappingError("record has neither numeroControlePNCP nor cnpj/year/sequence")
            control = f"{cnpj}-{year}-{sequence}"
        external_key = _normalize_key(control)
        description = _text(
            _first(record, "objetoCompra", "objeto", "description", "descricao", "descricaoObjeto", "objeto_compra")
        )
        purchase_number = _text(
            _first(record, "numeroCompra", "numero", "numeroEdital", "numeroAviso", "title")
        )
        title = _build_title(purchase_number, description, control)
        source_url = _text(_first(record, "linkSistemaOrigem", "link_sistema_origem", "source_url"))
        detail_url = _pncp_detail_url(cnpj, year, sequence)
        embedded_items = _list_from(record, "itens", "items", "listaItens")
        embedded_documents = _list_from(record, "documentos", "arquivos", "anexos")
        return NormalizedOpportunity(
            external_key=external_key,
            source=self.source,
            pncp_control_number=control,
            source_cnpj=cnpj,
            year=year,
            sequence=sequence,
            process_number=_text(_first(record, "processo", "numeroProcesso", "numero_processo")),
            title=title,
            description=description,
            buyer_name=_text(
                _first(
                    record,
                    "orgaoEntidade.razaoSocial",
                    "orgaoEntidadeRazaoSocial",
                    "orgao_nome",
                    "orgaoNome",
                    "nomeOrgao",
                )
            ),
            buyer_cnpj=_digits(
                _first(
                    record,
                    "orgaoEntidade.cnpj",
                    "orgaoEntidadeCnpj",
                    "orgao_cnpj",
                    "cnpjOrgao",
                    "numeroCnpj",
                )
            )
            or cnpj,
            uf=_upper(_first(
                record,
                "unidadeOrgao.ufSigla",
                "unidadeOrgaoUfSigla",
                "uf",
                "ufSigla",
                "unidade_uf",
            )),
            city=_text(
                _first(
                    record,
                    "unidadeOrgao.municipioNome",
                    "unidadeOrgaoMunicipioNome",
                    "municipio_nome",
                    "municipioNome",
                    "cidade",
                )
            ),
            uasg=_text(
                _first(
                    record,
                    "unidadeOrgao.codigoUnidade",
                    "unidadeOrgaoCodigoUnidade",
                    "unidade_codigo",
                    "codigoUnidadeCompradora",
                    "uasg",
                )
            ),
            modality=_text(
                _first(record, "modalidadeNome", "modalidade_licitacao_nome", "modalidade", "modalidadeCompraNome")
            ),
            modality_code=_integer(
                _first(
                    record,
                    "modalidadeId",
                    "modalidadeIdPncp",
                    "modalidade_licitacao_id",
                    "codigoModalidadeContratacao",
                )
            ),
            status=_status(record),
            estimated_value=_number(
                _first(record, "valorTotalEstimado", "valorTotal", "valor_global", "valorEstimado")
            ),
            published_at=_date_time(
                _first(record, "dataPublicacaoPncp", "dataPublicacaoPNCP", "data_publicacao_pncp", "dataPublicacao")
            ),
            proposal_start_at=_date_time(
                _first(
                    record,
                    "dataAberturaProposta",
                    "dataAberturaPropostaPncp",
                    "dataInicioProposta",
                    "data_inicio_vigencia",
                )
            ),
            proposal_end_at=_date_time(
                _first(
                    record,
                    "dataEncerramentoProposta",
                    "dataEncerramentoPropostaPncp",
                    "dataFimProposta",
                    "data_fim_vigencia",
                )
            ),
            source_url=source_url or detail_url,
            detail_url=detail_url,
            origin_url=source_url,
            items=self.map_items(items if items is not None else embedded_items),
            documents=self.map_documents(
                documents if documents is not None else embedded_documents,
                default_source=self.source,
            ),
        )

    def identify(self, payload: dict[str, Any]) -> tuple[str | None, int | None, int | None]:
        cnpj = _digits(_first(payload, "numeroCnpj", "cnpj", "orgao_cnpj", "orgaoEntidade.cnpj")) or None
        year = _integer(_first(payload, "anoCompra", "ano", "ano_compra"))
        sequence = _integer(
            _first(payload, "sequencialCompra", "numeroSequencial", "numero_sequencial", "sequencial")
        )
        return cnpj, year, sequence

    def map_items(self, payloads: list[dict[str, Any]]) -> list[OpportunityItem]:
        mapped: list[OpportunityItem] = []
        used_numbers: set[tuple[str, str]] = set()
        for position, payload in enumerate(payloads, 1):
            number = _text(_first(payload, "numeroItem", "numero", "item", "item_number")) or str(position)
            group = _text(_first(payload, "numeroGrupo", "grupo", "lote", "numeroLote")) or ""
            original_number = number
            duplicate = 2
            while (group, number) in used_numbers:
                number = f"{original_number}.{duplicate}"
                duplicate += 1
            used_numbers.add((group, number))
            description = _join_unique_text(
                _text(
                    _first(
                        payload,
                        "descricao",
                        "descricaoItem",
                        "objeto",
                        "description",
                        "itemDescricao",
                        "descricaoCompleta",
                        "descricaoDetalhada",
                    )
                ),
                _text(
                    _first(
                        payload,
                        "informacaoComplementar",
                        "informacoesComplementares",
                        "especificacao",
                        "especificacaoTecnica",
                        "complementoDescricao",
                        "detalhamento",
                        "observacao",
                        "observacoes",
                    )
                ),
            )
            label = f"Lote {group} - Item {number}" if group else f"Item {number}"
            title = _text(_first(payload, "materialOuServicoNome", "titulo", "title")) or description or label
            technical = _text(
                _first(
                    payload,
                    "criterioJulgamentoNome",
                    "criterioJulgamento",
                    "criterio_julgamento",
                    "technical_object",
                )
            )
            if group:
                technical = f"Lote {group}" + (f"; {technical}" if technical else "")
            unit_value = _number(
                _first(payload, "valorUnitarioEstimado", "valorUnitario", "estimated_unit_value")
            )
            quantity = _number(_first(payload, "quantidade", "quantidadeItem", "quantity"))
            total_value = _number(
                _first(payload, "valorTotal", "valorTotalEstimado", "estimated_total_value")
            )
            if total_value is None and unit_value is not None and quantity is not None:
                total_value = round(unit_value * quantity, 4)
            mapped.append(
                OpportunityItem(
                    source_item_id=_text(
                        _first(payload, "id", "numeroItem", "codigoItem", "source_item_id")
                    ),
                    item_number=number,
                    title=title,
                    lot_number=group,
                    description=description,
                    technical_object=technical,
                    quantity=quantity,
                    unit=_text(_first(payload, "unidadeMedida", "unidade", "unit")),
                    estimated_unit_value=unit_value,
                    estimated_total_value=total_value,
                    status=_text(
                        _first(payload, "situacaoCompraItemNome", "situacao", "status")
                    ),
                    granularity=_item_granularity(payload, group),
                    confidence=_item_confidence(payload, description),
                )
            )
        return mapped

    def map_documents(
        self,
        payloads: list[dict[str, Any]],
        *,
        default_source: str,
    ) -> list[OpportunityDocument]:
        mapped: list[OpportunityDocument] = []
        seen_urls: set[str] = set()
        for payload in payloads:
            url = _text(
                _first(payload, "url", "uri", "link", "urlArquivo", "linkDocumento", "downloadUrl")
            )
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            filename = _text(_first(payload, "nome", "nomeArquivo", "filename", "titulo"))
            document_type = _text(
                _first(payload, "tipoDocumentoNome", "tipo", "document_type", "tipoDocumento")
            ) or "anexo"
            mapped.append(
                OpportunityDocument(
                    document_type=document_type,
                    title=_text(_first(payload, "titulo", "descricao", "title")) or filename,
                    url=url,
                    filename=filename or _filename_from_url(url),
                    mime_type=_text(_first(payload, "tipoArquivo", "mimeType", "mime_type")),
                    source=default_source,
                )
            )
        return mapped


class ComprasGovMapper(PNCPMapper):
    source = "comprasgov"

    def map(self, payload: dict[str, Any], **kwargs: Any) -> NormalizedOpportunity:
        normalized = super().map(payload, **kwargs)
        normalized.source = self.source
        for document in normalized.documents:
            document.source = self.source
        return normalized


def _first(data: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = data
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                current = None
                break
            current = current[part]
        if current is not None and current != "":
            return current
    return None


def _list_from(data: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _list_from(value, "data", "items", "content", "resultado")
            if nested:
                return nested
    return []


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        elif value is not None and value != "":
            result[key] = value
    return result


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split()).strip()
    if not text:
        return None
    if "\u00c3" in text or "\u00c2" in text:
        try:
            repaired = text.encode("latin-1").decode("utf-8")
            if repaired:
                text = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def _join_unique_text(*values: str | None) -> str | None:
    parts: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text:
            continue
        folded = unicodedata.normalize("NFKC", text).casefold()
        if folded in seen:
            continue
        if any(folded in existing or existing in folded for existing in seen):
            continue
        seen.add(folded)
        parts.append(text)
    return " - ".join(parts) if parts else None


def _upper(value: Any) -> str | None:
    text = _text(value)
    return text.upper() if text else None


def _digits(value: Any) -> str:
    return "".join(character for character in str(value or "") if character.isdigit())


def _integer(value: Any) -> int | None:
    try:
        return int(str(value).strip()) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    text = re.sub(r"[^0-9,.-]", "", str(value))
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return None


def _item_granularity(payload: dict[str, Any], group: str) -> str:
    value = _text(_first(payload, "granularity", "granularidade", "nivelDetalhe"))
    if value:
        return value
    return "lote_item" if group else "item"


def _item_confidence(payload: dict[str, Any], description: str | None) -> float:
    explicit = _number(_first(payload, "confidence", "confianca", "scoreConfianca"))
    if explicit is not None:
        return max(0.0, min(float(explicit), 1.0))
    return 1.0 if description else 0.6


def _date_time(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    if re.fullmatch(r"\d{8}", text):
        try:
            return datetime.strptime(text, "%Y%m%d").date().isoformat()
        except ValueError:
            return text
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            return text


def _status(record: dict[str, Any]) -> str | None:
    if record.get("cancelado") is True:
        return "cancelled"
    return _text(
        _first(
            record,
            "situacaoCompraNome",
            "situacaoCompraNomePncp",
            "situacao_nome",
            "situacao",
            "status",
            "statusCompra",
        )
    )


def _normalize_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().upper()
    return re.sub(r"\s+", "", normalized)


def _build_title(number: str | None, description: str | None, control: str) -> str:
    if number:
        return f"Edital {number}"
    if description:
        return description[:180]
    return f"Oportunidade {control}"


def _pncp_detail_url(cnpj: str | None, year: int | None, sequence: int | None) -> str | None:
    if cnpj and year is not None and sequence is not None:
        return f"https://pncp.gov.br/app/editais/{cnpj}/{year}/{sequence}"
    return None


def _filename_from_url(url: str) -> str | None:
    path = urlparse(url).path.rstrip("/")
    return path.rsplit("/", 1)[-1] or None
