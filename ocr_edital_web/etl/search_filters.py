"""Shared normalization and object-type rules for opportunity searches."""

from __future__ import annotations

import re
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

MAX_SEARCH_TERM_GAP = 2


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


def search_word_variants(word: Any) -> set[str]:
    """Return common Portuguese singular/plural variants for a search word."""
    normalized = " ".join(re.findall(r"[a-z0-9]+", fold_search_text(word)))
    if not normalized or " " in normalized:
        return set()
    variants = {normalized}
    if len(normalized) > 3:
        if normalized.endswith("oes"):
            variants.add(f"{normalized[:-3]}ao")
        if normalized.endswith("ais"):
            variants.add(f"{normalized[:-3]}al")
        if normalized.endswith("eis"):
            variants.add(f"{normalized[:-3]}el")
        if normalized.endswith("is"):
            variants.add(f"{normalized[:-2]}il")
        if normalized.endswith("es"):
            variants.add(normalized[:-2])
        if normalized.endswith("s"):
            variants.add(normalized[:-1])
        variants.add(f"{normalized}s")
        if normalized[-1] in {"r", "z", "n"}:
            variants.add(f"{normalized}es")
        if normalized.endswith("al"):
            variants.add(f"{normalized[:-2]}ais")
        if normalized.endswith("el"):
            variants.add(f"{normalized[:-2]}eis")
        if normalized.endswith("ao"):
            variants.add(f"{normalized[:-2]}oes")
    return {variant for variant in variants if variant}


def matches_complete_words(text: Any, search_term: Any) -> bool:
    """Match complete words, their variants and short gaps inside a phrase."""
    expected = re.findall(r"[a-z0-9]+", fold_search_text(search_term))
    if not expected:
        return True
    words = re.findall(r"[a-z0-9]+", fold_search_text(text))
    expected_variants = [search_word_variants(word) for word in expected]
    for start, word in enumerate(words):
        if word not in expected_variants[0]:
            continue
        position = start
        for variants in expected_variants[1:]:
            stop = min(len(words), position + MAX_SEARCH_TERM_GAP + 2)
            next_position = next(
                (
                    index
                    for index in range(position + 1, stop)
                    if words[index] in variants
                ),
                None,
            )
            if next_position is None:
                break
            position = next_position
        else:
            return True
    return False


def search_term_matches(text: Any, search_term: Any) -> int:
    """SQLite-compatible wrapper for the complete-word matcher."""
    return int(matches_complete_words(text, search_term))


def is_single_word_search_term(search_term: Any) -> bool:
    """Return whether FTS token matching fully validates this search term."""
    return len(re.findall(r"[a-z0-9]+", fold_search_text(search_term))) == 1


def build_fts_query(search_terms: list[str]) -> str:
    """Build a safe FTS5 candidate query with morphological alternatives."""
    alternatives = []
    for search_term in search_terms:
        words = re.findall(r"[a-z0-9]+", fold_search_text(search_term))
        if not words:
            continue
        groups = []
        for word in words:
            variants = sorted(search_word_variants(word))
            groups.append("(" + " OR ".join(f'\"{variant}\"' for variant in variants) + ")")
        alternatives.append("(" + " AND ".join(groups) + ")")
    return " OR ".join(alternatives)


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
