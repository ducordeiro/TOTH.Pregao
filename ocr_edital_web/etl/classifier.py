"""Explainable, deterministic opportunity scoring."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any

from .models import MatchResult, NormalizedOpportunity


class OpportunityClassifier:
    WEIGHTS = {
        "keywords": 40.0,
        "items": 20.0,
        "regions": 15.0,
        "modalities": 10.0,
        "value": 10.0,
        "deadline": 5.0,
    }

    def classify(
        self,
        opportunity: NormalizedOpportunity,
        profile: dict[str, Any] | None = None,
    ) -> MatchResult:
        profile = profile or {}
        result = MatchResult(company_profile_id=str(profile.get("id") or "default"))
        earned = 0.0
        available = 0.0

        searchable = _fold(" ".join(filter(None, [opportunity.title, opportunity.description])))
        keywords = _strings(profile.get("keywords"))
        if keywords:
            available += self.WEIGHTS["keywords"]
            result.matched_keywords = [word for word in keywords if _fold(word) in searchable]
            if result.matched_keywords:
                ratio = len(result.matched_keywords) / len(keywords)
                earned += self.WEIGHTS["keywords"] * ratio
                result.reasons.append(
                    f"Palavras-chave aderentes: {', '.join(result.matched_keywords)}."
                )

        item_terms = _strings(profile.get("item_keywords") or profile.get("items"))
        if item_terms:
            available += self.WEIGHTS["items"]
            matched_items: list[str] = []
            for item in opportunity.items:
                item_text = _fold(" ".join(filter(None, [item.title, item.description])))
                if any(_fold(term) in item_text for term in item_terms):
                    matched_items.append(item.title)
            result.matched_items = list(dict.fromkeys(matched_items))
            if result.matched_items:
                earned += self.WEIGHTS["items"]
                result.reasons.append(f"{len(result.matched_items)} item(ns) aderente(s) ao perfil.")

        ufs = [value.upper() for value in _strings(profile.get("ufs"))]
        cities = [_fold(value) for value in _strings(profile.get("cities"))]
        if ufs or cities:
            available += self.WEIGHTS["regions"]
            if opportunity.uf and opportunity.uf.upper() in ufs:
                result.matched_regions.append(opportunity.uf.upper())
            if opportunity.city and _fold(opportunity.city) in cities:
                result.matched_regions.append(opportunity.city)
            if result.matched_regions:
                earned += self.WEIGHTS["regions"]
                result.reasons.append(f"Regiao atendida: {', '.join(result.matched_regions)}.")

        modalities = _strings(profile.get("modalities"))
        if modalities:
            available += self.WEIGHTS["modalities"]
            modality = _fold(opportunity.modality or "")
            result.matched_modalities = [value for value in modalities if _fold(value) in modality]
            if result.matched_modalities:
                earned += self.WEIGHTS["modalities"]
                result.reasons.append(f"Modalidade aderente: {opportunity.modality}.")

        minimum = _float(profile.get("min_estimated_value"))
        maximum = _float(profile.get("max_estimated_value"))
        if minimum is not None or maximum is not None:
            available += self.WEIGHTS["value"]
            value = opportunity.estimated_value
            if value is not None and (minimum is None or value >= minimum) and (maximum is None or value <= maximum):
                earned += self.WEIGHTS["value"]
                result.reasons.append("Valor estimado dentro da faixa configurada.")

        minimum_days = _float(profile.get("min_deadline_days"))
        if minimum_days is not None:
            available += self.WEIGHTS["deadline"]
            days = _days_until(opportunity.proposal_end_at)
            if days is not None and days >= minimum_days:
                earned += self.WEIGHTS["deadline"]
                result.reasons.append(f"Prazo restante de {days:.1f} dia(s).")

        result.score = round((earned / available * 100.0) if available else 0.0, 2)
        if not available:
            result.reasons.append("Perfil sem criterios de classificacao configurados.")
        elif not result.reasons:
            result.reasons.append("Nenhum criterio configurado foi atendido.")
        return result


def _fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character)).casefold()


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _days_until(value: str | None) -> float | None:
    if not value:
        return None
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
        now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.now()
        return (deadline - now).total_seconds() / 86400
    except ValueError:
        return None
