"""Block 7 reference retrieval, separate from product compliance decisions."""

import json
import math
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

LIBRARY = Path(__file__).parent / "resources" / "catalog_library" / "references.json"
STOP_WORDS = set("para como pela pelo pelo pelas pelos entre conforme minimo minima maxima maximo altura largura profundidade cadeira cadeiras produto modelo catalogo goldflex item itens deve devera sera sobre possui deve sendo suas seus esse esta este uma com sem dos das que nao por nos nas das mm cm".split())


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower()) if not unicodedata.combining(c))


def tokens(value):
    return {word for word in re.findall(r"[a-z0-9]+", normalized(value))
            if len(word) >= 4 and word not in STOP_WORDS}


@lru_cache(maxsize=1)
def library_index():
    manifest = json.loads(LIBRARY.read_text(encoding="utf-8"))
    entries = []
    frequency = Counter()
    for row in manifest["documents"]:
        if row["kind"] == "requisito_edital" or not row["text"].strip():
            continue
        words = tokens(row["text"])
        frequency.update(words)
        entries.append((row, words, tokens(row["source"])))
    return manifest, entries, frequency


def library_summary():
    manifest, entries, _ = library_index()
    return {"documents": len(manifest["documents"]), "searchable_reports": len(entries),
            "documented_models": len(manifest.get("products", [])),
            "source": manifest["archive_name"], "automatic_compliance": False}


@lru_cache(maxsize=256)
def _reference_locations(document_id):
    row = next(row for row, _, _ in library_index()[1] if row["id"] == document_id)
    locations = row.get("locations") or [{"text": row["text"]}]
    return tuple((location, tokens(location["text"]), tuple(
        (line.strip(), tokens(line.strip())) for line in location["text"].splitlines()
        if line.strip() and not line.startswith("#")
    )) for location in locations)


@lru_cache(maxsize=256)
def _find_references(text):
    # A shared material alone must not associate unrelated products with chairs.
    if not re.search(r"\b(cadeiras?|poltronas?|mochos?|banquetas?|assentos?|longarinas?|bancos?)\b", normalized(text)):
        return ()
    query = tokens(text)
    _, entries, frequency = library_index()
    matches = []
    for row, words, title in entries:
        shared = query & words
        if len(shared) < 2:
            continue
        score = sum(math.log(1 + len(entries) / frequency[w]) * (3 if w in title else 1) for w in shared)
        matches.append((score, row["source"], row, shared))
    matches.sort(key=lambda match: (-match[0], match[1]))
    results = []
    # Locate excerpts only for displayed references; reuse tokenized pages across items.
    for _, _, row, shared in matches[:5]:
        location, _, lines = max(_reference_locations(row["id"]), key=lambda entry: len(entry[1] & shared))
        excerpt, _ = max(lines, key=lambda entry: len(entry[1] & shared), default=("", set()))
        results.append({
            "id": row["id"], "fonte": row["source"], "sha256": row["sha256"],
            "trecho": excerpt[:900], "tipo": row["kind"],
            "pagina": location.get("page"), "secao": location.get("section"),
            "estado": "referencia_para_revisao",
            "nota": ("Revisão alternativa do inventário; não substitui a revisão atual. " if row["kind"] == "inventario_variante" else "")
                    + "Referência documental: conferir o vínculo com o modelo e a configuração. Não comprova atendimento automaticamente.",
        })
    return tuple(results)


def find_catalog_references(text):
    return [dict(row) for row in _find_references(text)]
