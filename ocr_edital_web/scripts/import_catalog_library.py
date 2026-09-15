"""Import reference documents only; never execute or install archive contents."""

import argparse
import hashlib
import json
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "relatoriocatalogogoldflex/Modelos de catalogos/"


def import_library(archive, destination):
    documents = []
    seen = set()
    destination.mkdir(parents=True, exist_ok=True)
    originals = ROOT / "data" / "catalog_repertoire" / "originals"
    originals.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            if not entry.filename.startswith(PREFIX) or entry.is_dir():
                continue
            suffix = Path(entry.filename).suffix.lower()
            if suffix not in {".md", ".txt", ".pdf", ".docx"}:
                continue
            if entry.file_size > 30 * 1024 * 1024:
                raise ValueError(f"Reference too large: {entry.filename}")
            raw = source.read(entry)
            digest = hashlib.sha256(raw).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            relative = entry.filename[len(PREFIX):]
            text = raw.decode("utf-8-sig", errors="replace") if suffix in {".md", ".txt"} else ""
            normalized = unicodedata.normalize("NFKD", relative).encode("ascii", "ignore").decode().lower()
            kind = "analise_historica" if suffix == ".md" else "documento_original"
            if "pedido edital" in normalized or "analises de editais/" in normalized:
                kind = "requisito_edital"
            record = {
                "id": digest, "source": relative, "sha256": digest,
                "kind": kind, "format": suffix, "text": text,
                "original": f"data/catalog_repertoire/originals/{digest}{suffix}",
            }
            target = originals / f"{digest}{suffix}"
            if not target.exists():
                target.write_bytes(raw)
            elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Original checksum mismatch: {target}")
            documents.append(record)
    manifest = {"schema_version": 1, "archive_name": Path(archive).name,
                "documents": sorted(documents, key=lambda row: row["source"])}
    (destination / "references.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(documents), "searchable": sum(bool(d["text"]) and d["kind"] != "requisito_edital" for d in documents)}, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    import_library(args.archive, ROOT / "resources" / "catalog_library")
