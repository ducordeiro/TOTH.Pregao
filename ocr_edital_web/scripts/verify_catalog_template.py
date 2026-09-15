"""Offline Block 7 template regression using the supplied Word template."""
import argparse
import hashlib
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from catalog_generator import export_catalog, normalize_items
from server import convert_docx_to_pdf


def verify(template):
    output = ROOT / "reports/catalog-template"
    output.mkdir(parents=True, exist_ok=True)
    items = normalize_items([{"numeroItem": 1, "descricao": "Cadeira giratória em tela Mesh com apoio lombar e pistão classe 4", "quantidade": 1, "unidade": "UN"}], "offline:template-test")
    start = time.perf_counter()
    exports = export_catalog(output, {}, items, "template-verification", template, convert_docx_to_pdf)
    generated = output / exports["docx"]["filename"]
    with zipfile.ZipFile(template) as original, zipfile.ZipFile(generated) as final:
        preserved = [name for name in original.namelist() if name.startswith(("word/media/", "word/header", "word/footer")) or name in {"word/styles.xml", "word/numbering.xml"}]
        changed = [name for name in preserved if original.read(name) != final.read(name)]
        if changed:
            raise AssertionError(f"Template parts changed: {changed}")
    result = {"template": str(template), "sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
              "seconds": round(time.perf_counter() - start, 2), "preserved_parts": preserved, "exports": exports}
    if "pdf" in exports:
        import pdfplumber
        with pdfplumber.open(output / exports["pdf"]["filename"]) as pdf:
            result["pages"] = len(pdf.pages)
            for index, page in enumerate(pdf.pages, 1):
                page.to_image(resolution=120).save(output / f"page-{index}.png")
    (output / "verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template", type=Path)
    verify(parser.parse_args().template)
