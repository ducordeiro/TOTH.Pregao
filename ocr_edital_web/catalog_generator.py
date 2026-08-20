import csv
import json
import re
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


MANUFACTURER = {
    "razao_social": "GOLDFLEX INDUSTRIA E COMERCIO DE MOVEIS E EQUIPAMENTOS LTDA",
    "cnpj": "33.661.439/0001-14",
}

EXPORT_COLUMNS = (
    ("numero", "Item"),
    ("codigo", "Código"),
    ("produto", "Produto"),
    ("descricao", "Descrição"),
    ("especificacao_tecnica", "Especificação técnica"),
    ("unidade", "Unidade"),
    ("quantidade", "Quantidade"),
    ("marca_referencia", "Marca/referência"),
    ("valor_estimado", "Valor estimado"),
    ("criterios_aceitacao", "Critérios de aceitação"),
    ("observacoes", "Observações"),
    ("categoria", "Categoria"),
    ("subcategoria", "Subcategoria"),
    ("status_evidencia", "Evidência"),
)


def compact(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def item_number(item, index):
    return compact(item.get("item") or item.get("numero") or item.get("numeroItem")) or str(index + 1)


def classify_item(description):
    text = compact(description).lower()
    rules = (
        (("cadeira", "poltrona", "longarina", "banqueta"), ("Mobiliário", "Assentos")),
        (("mesa", "estação de trabalho"), ("Mobiliário", "Mesas")),
        (("armário", "arquivo", "gaveteiro", "estante"), ("Mobiliário", "Armazenamento")),
        (("computador", "notebook", "monitor"), ("Tecnologia", "Equipamentos")),
    )
    for terms, category in rules:
        if any(term in text for term in terms):
            return category
    return "Não classificado", ""


def normalize_items(items, source_url, source_name="API oficial do PNCP"):
    normalized = []
    seen = set()
    for index, raw in enumerate(items or []):
        description = compact(
            raw.get("descricao") or raw.get("description") or raw.get("objeto")
        )
        number = item_number(raw, index)
        key = (number, description.lower())
        if key in seen:
            continue
        seen.add(key)
        category, subcategory = classify_item(description)
        item_source = compact(raw.get("_catalog_source_name")) or source_name
        missing = [
            label
            for field, label in (("descricao", "descrição"), ("quantidade", "quantidade"), ("unidade", "unidade"))
            if not compact(raw.get(field)) and not (field == "descricao" and description)
        ]
        normalized.append({
            "id": f"item-{index + 1}",
            "numero": number,
            "codigo": compact(raw.get("codigo") or raw.get("codigoItem") or raw.get("material")),
            "produto": compact(raw.get("produto") or raw.get("nome") or raw.get("_nome")) or description[:120],
            "descricao": description,
            "especificacao_tecnica": compact(raw.get("especificacao_tecnica") or raw.get("especificacao") or description),
            "unidade": compact(raw.get("unidade") or raw.get("unidadeMedida")),
            "quantidade": compact(raw.get("quantidade") or raw.get("quantidadeItem")),
            "marca_referencia": compact(raw.get("marca_referencia") or raw.get("marca")),
            "valor_estimado": raw.get("valor_estimado") or raw.get("valorUnitarioEstimado") or "",
            "criterios_aceitacao": compact(raw.get("criterios_aceitacao")),
            "observacoes": compact(raw.get("observacoes")),
            "categoria": category,
            "subcategoria": subcategory,
            "status_evidencia": "confirmado" if description else "incompleto",
            "campos_ausentes": missing,
            "conflitos": [],
            "fontes": [{
                "documento": item_source,
                "pagina": None,
                "secao": f"Item {number}",
                "url": source_url,
            }],
        })
    return normalized


def validation_summary(items):
    incomplete = sum(bool(item.get("campos_ausentes")) for item in items)
    conflicts = sum(bool(item.get("conflitos")) for item in items)
    warnings = []
    if incomplete:
        warnings.append(f"{incomplete} item(ns) possuem campos obrigatórios ausentes.")
    if conflicts:
        warnings.append(f"{conflicts} item(ns) possuem divergências entre fontes.")
    if not items:
        warnings.append("Nenhum item foi identificado nas fontes disponíveis.")
    return {"incompletos": incomplete, "conflitos": conflicts, "avisos": warnings}


def sanitize_export_items(items):
    clean = []
    for index, raw in enumerate(items or []):
        item = {key: raw.get(key, "") for key, _ in EXPORT_COLUMNS}
        item["numero"] = compact(item["numero"]) or str(index + 1)
        item["fontes"] = raw.get("fontes") if isinstance(raw.get("fontes"), list) else []
        item["campos_ausentes"] = raw.get("campos_ausentes") if isinstance(raw.get("campos_ausentes"), list) else []
        clean.append(item)
    return clean


def export_catalog(output_dir, metadata, items, job_id):
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_items = sanitize_export_items(items)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"catalogo_pncp_{job_id[:8]}_{stamp}"

    json_path = output_dir / f"{stem}.json"
    json_path.write_text(json.dumps({
        "fabricante": MANUFACTURER,
        "edital": metadata,
        "itens": safe_items,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = output_dir / f"{stem}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[key for key, _ in EXPORT_COLUMNS], extrasaction="ignore", delimiter=";")
        writer.writeheader()
        writer.writerows(safe_items)

    xlsx_path = output_dir / f"{stem}.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Catálogo"
    sheet.append([label for _, label in EXPORT_COLUMNS])
    for item in safe_items:
        sheet.append([item.get(key, "") for key, _ in EXPORT_COLUMNS])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column) + 2, 48)
        sheet.column_dimensions[column[0].column_letter].width = width
    workbook.save(xlsx_path)

    pdf_path = output_dir / f"{stem}.pdf"
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(pdf_path), pagesize=landscape(A4), rightMargin=10 * mm, leftMargin=10 * mm, topMargin=10 * mm, bottomMargin=10 * mm)
    story = [Paragraph("Catálogo de itens da licitação", styles["Title"]), Paragraph(compact(metadata.get("objeto")) or "Objeto não informado", styles["BodyText"]), Spacer(1, 5 * mm)]
    pdf_columns = (("numero", "Item"), ("produto", "Produto"), ("descricao", "Descrição"), ("unidade", "Un."), ("quantidade", "Qtd."), ("valor_estimado", "Valor"), ("status_evidencia", "Evidência"))
    rows = [[Paragraph(label, styles["BodyText"]) for _, label in pdf_columns]]
    for item in safe_items:
        rows.append([Paragraph(compact(item.get(key))[:800], styles["BodyText"]) for key, _ in pdf_columns])
    table = Table(rows, repeatRows=1, colWidths=[14 * mm, 36 * mm, 105 * mm, 15 * mm, 18 * mm, 24 * mm, 24 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#233254")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B7B7C2")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F5")]),
    ]))
    story.append(table)
    document.build(story)

    return {
        kind: {"filename": path.name, "download_url": f"/download/{path.name}"}
        for kind, path in (("xlsx", xlsx_path), ("csv", csv_path), ("json", json_path), ("pdf", pdf_path))
    }
