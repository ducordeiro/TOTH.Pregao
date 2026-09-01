from pathlib import Path
import re
from pypdf import PdfReader

ROOT = Path(r"Modelos de catalogos\catalogos de pedidos")

def clean(text):
    text = text.replace("\u00a0", " ").replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line and (not lines or line != lines[-1]): lines.append(line)
    return lines

def classify(name, text):
    x = (name + " " + text).lower()
    movement = []
    if any(k in x for k in ("girat", "giro", "rodízio", "rodizio", "pistão", "pistao")): movement.append("giratória/giratória conforme descrição")
    if any(k in x for k in ("fixa", "fixo", "empilh")): movement.append("fixa/empilhável conforme descrição")
    if any(k in x for k in ("auditório", "auditorio", "poltrona")): movement.append("auditório/poltrona")
    if any(k in x for k in ("mocho", "semi-sentado", "semi sentado")): movement.append("mocho ou semi-sentado")
    categories = []
    for key, label in (("polipropileno", "polipropileno"), ("poliuretano", "poliuretano/PU"), ("tela", "tela"), ("estof", "estofada"), ("prancheta", "com prancheta"), ("longarina", "longarina")):
        if key in x and label not in categories: categories.append(label)
    return "; ".join(movement) or "não classificado automaticamente", "; ".join(categories) or "não classificada automaticamente"

def lines_matching(lines, patterns):
    out = []
    for line in lines:
        low = line.lower()
        if any(p in low for p in patterns):
            if line not in out: out.append(line)
    return out

def extract(folder):
    pdfs = sorted(folder.glob("*.pdf"))
    txts = sorted(folder.glob("*.txt"))
    docs = []
    all_text = []
    for f in pdfs:
        reader = PdfReader(str(f)); pages = []
        for n, page in enumerate(reader.pages, 1):
            lines = clean(page.extract_text() or "")
            pages.append((n, lines)); all_text += lines
        docs.append((f.name, len(reader.pages), pages))
    for f in txts:
        raw = f.read_text(encoding="utf-8", errors="replace")
        lines = clean(raw); all_text += lines
        docs.append((f.name, None, [(None, lines)]))
    return docs, all_text

def md_escape(text):
    return text.replace("|", "\\|")

def build(folder):
    out = folder / "laudo-tecnico-consolidado.md"
    if out.exists(): return False
    docs, all_lines = extract(folder)
    if not docs: return False
    movement, category = classify(folder.name, " ".join(all_lines))
    measures = lines_matching(all_lines, ["medida", "dimens", "altura", "largura", "profundidade", "espessura", "diâmetro", "diametro", "seção", "secao", "curso", "mm", " cm"])
    components = lines_matching(all_lines, ["assento", "encosto", "estrutura", "base", "rodízio", "rodizio", "pistão", "pistao", "mecanismo", "revestimento", "tecido", "cor", "espuma", "polipropileno", "poliuretano", "solda", "pintura", "tratamento", "prancheta", "braço", "braco", "sapata", "ponteira"])
    capacity_norms = lines_matching(all_lines, ["kg", "nbr", "nr 17", "garantia", "norma", "laudo", "ensaio", "certif"])
    lines = [
        f"# Laudo técnico consolidado — {folder.name}", "", "## 1. Escopo e limite", "",
        "Este laudo foi criado a partir dos arquivos encontrados nesta pasta. Ele registra evidências textuais dos catálogos e documentos associados, com referência ao arquivo e à página. Não transforma ausência de informação em conformidade e não substitui amostra, ficha técnica, laudo ou ensaio original.", "",
        "## 2. Documentos avaliados", ""
    ]
    for name, pages, _ in docs:
        lines.append(f"- `{name}`" + (f", {pages} páginas" if pages else ", arquivo textual associado"))
    lines += ["", "## 3. Classificação inicial", "", f"- Tipo de movimento/família identificado no conjunto: **{movement}**.", f"- Categoria construtiva identificada no conjunto: **{category}**.", "- A classificação automática deve ser conferida com o título e a descrição específica de cada catálogo.", ""]
    lines += ["## 4. Medidas e dimensões encontradas", ""]
    if measures:
        lines += [f"- {md_escape(x)}" for x in measures]
    else: lines.append("- Nenhuma linha dimensional foi localizada na extração textual.")
    lines += ["", "## 5. Materiais, componentes e acabamentos encontrados", ""]
    if components:
        lines += [f"- {md_escape(x)}" for x in components]
    else: lines.append("- Nenhuma descrição técnica de componentes foi localizada na extração textual.")
    lines += ["", "## 6. Capacidade, normas, garantia e documentos citados", ""]
    if capacity_norms:
        lines += [f"- {md_escape(x)}" for x in capacity_norms]
    else: lines.append("- Não localizados na extração textual.")
    lines += ["", "## 7. Lacunas de evidência", "", "- Dimensões ou características não presentes nas linhas extraídas permanecem não evidenciadas.", "- Declarações de norma, capacidade, garantia, laudo ou ensaio não foram tratadas como certificados revisados quando o documento apenas as menciona.", "- Fotografias, desenhos sem cota e nomes comerciais não foram usados para inventar materiais ou desempenho.", ""]
    lines += ["## 8. Rastreabilidade por arquivo e página", ""]
    for name, pages, page_data in docs:
        lines += [f"### `{name}`", ""]
        for page_no, page_lines in page_data:
            label = f"Página {page_no}" if page_no else "Conteúdo textual"
            lines.append(f"#### {label}")
            if page_lines:
                for line in page_lines:
                    lines.append(f"> {line.replace('>', '\\>')}")
            else: lines.append("> Sem texto extraível.")
            lines.append("")
    lines += ["## 9. Conclusão", "", "O conjunto documental foi registrado para integração à biblioteca de modelos. A decisão de oferta ou aceitação deve usar o catálogo específico, a configuração efetivamente ofertada e os documentos técnicos exigidos no respectivo processo.", ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return True

created = []
for folder in sorted(ROOT.iterdir()):
    if not folder.is_dir() or folder.name.lower() == "dados extraidos": continue
    if build(folder): created.append(folder.name)
print("created", len(created))
for x in created: print(x)
