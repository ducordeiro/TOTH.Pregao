"""Compare nested catalog packages by content, without executing their files."""
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
manifest_path = ROOT / "resources/catalog_library/references.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
known = {row["sha256"] for row in manifest["documents"]}
report = []


def inspect(archive_path):
    with zipfile.ZipFile(archive_path) as outer, tempfile.TemporaryDirectory(prefix="catalog-archive-") as temp:
        for member in outer.infolist():
            suffix = Path(member.filename).suffix.lower()
            if suffix not in {".rar", ".zip"}:
                continue
            data = outer.read(member)
            result = {"source": member.filename, "checked_documents": 0, "not_indexed": []}
            def record(name, content):
                if Path(name).suffix.lower() not in {".pdf", ".docx"} or "node_modules" in name:
                    return
                value = hashlib.sha256(content).hexdigest()
                result["checked_documents"] += 1
                if value not in known:
                    result["not_indexed"].append({"name": name, "sha256": value})
                    if "--retain-inventory" in sys.argv and Path(name).name == "validacao-modelos-cadeiras-por-categoria-v3.docx":
                        document = Document(io.BytesIO(content))
                        locations = [{"section": f"Parágrafo {index}", "text": paragraph.text}
                                     for index, paragraph in enumerate(document.paragraphs, 1) if paragraph.text.strip()]
                        locations.extend({"section": f"Tabela {index}, linha {number}", "text": " | ".join(cell.text for cell in row.cells)}
                                         for index, table in enumerate(document.tables, 1) for number, row in enumerate(table.rows, 1))
                        original = ROOT / "data/catalog_repertoire/originals" / f"{value}.docx"
                        original.write_bytes(content)
                        manifest["documents"].append({"id": value, "sha256": value,
                            "source": "Revisao alternativa do pacote do agente/" + Path(name).name,
                            "kind": "inventario_variante", "format": ".docx",
                            "original": original.relative_to(ROOT).as_posix(),
                            "text": "\n".join(location["text"] for location in locations),
                            "locations": locations, "scan_status": "text_extracted", "empty_pages": []})
                        known.add(value)
                        result["not_indexed"][-1]["retained_separately"] = True
            try:
                if suffix == ".zip":
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:
                        for item in nested.infolist():
                            if Path(item.filename).suffix.lower() in {".pdf", ".docx"} and "node_modules" not in item.filename:
                                record(item.filename, nested.read(item))
                else:
                    path = Path(temp) / (hashlib.sha256(data).hexdigest() + suffix)
                    path.write_bytes(data)
                    listing = subprocess.run(["tar", "-tf", str(path)], capture_output=True, check=True, timeout=30)
                    for name in listing.stdout.decode("utf-8", errors="replace").splitlines():
                        if Path(name).suffix.lower() in {".pdf", ".docx"}:
                            extracted = subprocess.run(["tar", "-xOf", str(path), "--", name], capture_output=True, check=True, timeout=30)
                            record(name, extracted.stdout)
            except Exception as exc:
                result["error"] = str(exc)
            report.append(result)
    if any(row.get("retained_separately") for entry in report for row in entry["not_indexed"]):
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "reports/catalog-library/nested-archives.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))


if __name__ == "__main__":
    inspect(sys.argv[1])
