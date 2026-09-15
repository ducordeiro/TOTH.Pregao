"""Read the supplied archive, verify retained references, and inventory technical evidence."""
import hashlib
import json
import shutil
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from catalog_technical_layout import folded, STANDARD_CLAUSES


def audit(archive_path, import_analyses=False):
    manifest_path = ROOT / "resources/catalog_library/references.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    known = {row["sha256"]: row for row in manifest["documents"]}
    files = []
    imported = []
    with zipfile.ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            digest = hashlib.sha256()
            with archive.open(entry) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            value = digest.hexdigest()
            relative = entry.filename.removeprefix("relatoriocatalogogoldflex/")
            if import_analyses and value not in known and relative.startswith("analises/") and Path(relative).suffix == ".md":
                if not imported:
                    backup = ROOT / "reports/catalog-library" / f"references-before-{datetime.now():%Y%m%d-%H%M%S}.json"
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(manifest_path, backup)
                data = archive.read(entry)
                text = data.decode("utf-8-sig")
                original = ROOT / "data/catalog_repertoire/originals" / f"{value}.md"
                original.write_bytes(data)
                row = {"id": value, "source": relative, "sha256": value, "kind": "relatorio_analise",
                       "format": ".md", "text": text, "original": original.relative_to(ROOT).as_posix(),
                       "locations": [{"section": "Relatório", "text": text}], "scan_status": "text_extracted", "empty_pages": []}
                manifest["documents"].append(row)
                known[value] = row
                imported.append(relative)
            files.append({"source": entry.filename, "bytes": entry.file_size, "sha256": value,
                          "indexed": value in known, "format": Path(entry.filename).suffix.lower()})
    if imported:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    terms = {
        "Compensado e fixacao": ("compensad", "porca", "garra"),
        "Espuma, densidade e CFC": ("espuma", "densidade", "cfc"),
        "Tubo e espessura": ("tubo", "espessura", "25x25", "50x30", "7/8"),
        "Solda MIG": ("solda mig", "soldagem mig"),
        "Tratamento e pintura": ("fosfor", "antiferrug", "estufa", "250"),
        "Normas": ("13962", "nr-17", "nr 17", "nr17"),
        "Carga e garantia": ("carga", "capacidade", "garantia"),
    }
    evidence = {}
    for topic, needles in terms.items():
        matches = []
        for row in manifest["documents"]:
            if row["kind"] == "requisito_edital":
                continue
            for location in row.get("locations") or [{"text": row["text"]}]:
                for line in location["text"].splitlines():
                    if any(needle in folded(line) for needle in needles):
                        matches.append({"source": row["source"], "sha256": row["sha256"],
                                        "page": location.get("page"), "section": location.get("section"),
                                        "excerpt": line.strip()[:1200]})
        evidence[topic] = matches
    reference_files = [row for row in files if row["indexed"] or any(folder in folded(row["source"])
                        for folder in ("/analises/", "/catalogos de pedidos/", "/laudos e ensaios/", "/validacao de dados/"))]
    unseen = [row for row in reference_files if not row["indexed"] and row["format"] in {".pdf", ".docx", ".txt", ".md"}]
    summary = {"archive": str(archive_path), "archive_files": len(files),
               "formats": dict(Counter(row["format"] for row in files)),
               "indexed_archive_files": sum(row["indexed"] for row in files),
               "indexed_unique_archive_documents": len({row["sha256"] for row in files if row["indexed"]}),
               "imported_analyses": imported,
               "unindexed_readable_files": unseen, "library_documents": len(known),
               "searchable_documents": sum(bool(row["text"].strip()) and row["kind"] != "requisito_edital" for row in known.values()),
               "needs_ocr": [row["source"] for row in known.values() if row.get("scan_status") == "needs_ocr"],
               "evidence_locations": {key: len(value) for key, value in evidence.items()},
               "exact_standard_clauses": {clause: [row["source"] for row in known.values()
                                                    if row["kind"] != "requisito_edital" and folded(clause) in folded(row["text"])]
                                          for _, clause in STANDARD_CLAUSES}}
    output = ROOT / "reports/catalog-library"
    output.mkdir(parents=True, exist_ok=True)
    (output / "source-audit.json").write_text(json.dumps({"summary": summary, "files": files, "evidence": evidence}, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Revisao das referencias do Bloco 7", "", f"Arquivo consultado: `{archive_path}`.",
             f"Arquivos no ZIP: {len(files)}; correspondencias por SHA-256: {summary['indexed_archive_files']}.",
             f"Biblioteca: {len(known)} documentos; {summary['searchable_documents']} pesquisaveis.",
             f"Referencias textuais do ZIP ainda fora do indice: {len(unseen)}. Codigo, dependencias e arquivos temporarios nao sao catalogos e foram excluidos dessa contagem.", "",
             "Referencias nao equivalem a conformidade de qualquer modelo. Medidas, laudos e limites devem permanecer vinculados ao produto e a configuracao ensaiada.", ""]
    for topic, matches in evidence.items():
        lines.extend(["## " + topic, "", f"{len(matches)} trechos localizados."])
        sources = set()
        for match in matches:
            if match["source"] in sources:
                continue
            sources.add(match["source"])
            location = f"pagina {match['page']}" if match["page"] else match["section"] or "texto"
            lines.append(f"- {match['source']} ({location}): {match['excerpt']}")
            if len(sources) == 5:
                break
        lines.append("")
    lines.extend(["## Clausulas padrao", "", "A ausencia da frase integral nao significa descumprimento, mas impede publica-la automaticamente como fato."])
    for clause, sources in summary["exact_standard_clauses"].items():
        lines.append(f"- {clause}: {len(sources)} documento(s) com a redacao integral.")
    (output / "source-audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key not in {"exact_standard_clauses", "unindexed_readable_files"}}, ensure_ascii=True))


if __name__ == "__main__":
    audit(Path(sys.argv[1]), import_analyses="--import-analyses" in sys.argv[2:])
