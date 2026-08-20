"""Shared normalization and object-type rules for opportunity searches."""

from __future__ import annotations

import unicodedata
from functools import lru_cache
from typing import Any


MATERIAL_SEARCH_TERMS = (
    "aquisicao", "compra", "fornecimento", "material", "materiais", "produto",
    "produtos", "equipamento", "equipamentos", "bem", "bens", "insumo",
    "insumos", "medicamento", "medicamentos", "mobiliario", "generos alimenticios",
    "microcomputador", "microcomputadores", "computador", "computadores",
    "desktop", "desktops", "notebook", "notebooks", "monitor", "monitores",
    "periferico", "perifericos", "informatica", "teclado", "mouse",
)

SERVICE_SEARCH_TERMS = (
    "prestacao de servico", "prestacao de servicos", "servico de", "servicos de",
    "manutencao", "locacao", "consultoria", "assessoria", "capacitacao",
    "treinamento", "transporte", "vigilancia", "obra", "reforma",
    "engenharia", "mao de obra", "licenca de uso",
)


def fold_search_text(value: Any) -> str:
    """Return lowercase, accent-free text with stable whitespace."""
    return _fold_search_text_cached(str(value or ""))


@lru_cache(maxsize=65_536)
def _fold_search_text_cached(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    plain_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(plain_text.lower().split())


def classify_object_text(value: Any) -> str:
    """Infer material/service from the available procurement description."""
    return _classify_object_text_cached(fold_search_text(value))


@lru_cache(maxsize=65_536)
def _classify_object_text_cached(text: str) -> str:
    material_score = sum(1 for term in MATERIAL_SEARCH_TERMS if term in text)
    service_score = sum(1 for term in SERVICE_SEARCH_TERMS if term in text)

    if (
        "contratacao de empresa para fornecimento" in text
        or "registro de preco" in text
        or "registro de precos" in text
    ):
        material_score += 2
    if "contratacao de empresa especializada" in text and "fornecimento" not in text:
        service_score += 2

    if material_score > service_score:
        return "material"
    if service_score > material_score:
        return "servico"
    return ""
