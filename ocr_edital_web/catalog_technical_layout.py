"""Editorial layout for Block 7. Never use bid requirements as product evidence."""
import re
import unicodedata


def folded(value):
    return " ".join("".join(character for character in unicodedata.normalize("NFKD", str(value))
                            if not unicodedata.combining(character)).lower().split())


STANDARD_CLAUSES = (
    ("ASSENTO E ENCOSTO", "madeira compensada multilaminada moldada anatomicamente a quente com bordas arredondadas e fixação por porcas garras"),
    ("ASSENTO E ENCOSTO", "espuma moldada/injetada de poliuretano de alta densidade, isenta de CFC"),
    ("ESTRUTURA METÁLICA / BASE", "submetida a pré-tratamento antiferrugens de desengraxe, estabilização, fosforização, pintura a pó eletrostática e secagem em estufa a 250°C"),
    ("ESTRUTURA METÁLICA / BASE", "unidos pelo sistema de solda MIG"),
    ("RESUMO DO ITEM", "NR-17 e ABNT NBR 13962/2018"),
)

# A matching sentence is shown verbatim; no numeric specification is synthesized.
SECTIONS = (
    ("RESUMO DO ITEM", (
        ("Cor", r"\bcor\b|\bcores\b|\bpreta?\b|\bazul\b|\bbranc[oa]\b"),
        ("Revestimento", r"revest|tecido|poliester|courvin|couro|vinil|tela"),
        ("Carga máxima suportada (kg)", r"capacidade|carga|suport"),
        ("Normas técnicas", r"\bnr[ -]?17\b|\bnbr\b|\babnt\b"),
    )),
    ("ASSENTO E ENCOSTO", (
        ("Compensado", r"compensad"),
        ("Fixação do assento e encosto", r"porcas? garras?|parafus|fixacao"),
        ("Espuma e densidade (kg/m³)", r"densidade.{0,50}\d|\d.{0,15}kg/m[³3]"),
        ("Dimensões do assento", r"assento.{0,60}(dimens|altura|largura|profund|\d)"),
        ("Dimensões do encosto", r"encosto.{0,60}(dimens|altura|largura|\d)"),
        ("Acabamentos", r"acabamento|bordas|costur|carenagem"),
    )),
    ("ESTRUTURA METÁLICA / BASE", (
        ("Seção do tubo de aço", r"tubo.{0,80}(?:\d|redond|quadr|retang|oblong)|secao.*aco"),
        ("Espessura do aço (mm)", r"(?:aco|tubo|chapa).{0,70}espessura|espessura.{0,70}(?:aco|tubo|chapa)"),
        ("Processo de solda", r"solda|soldagem"),
        ("Tratamento anticorrosivo e pintura", r"anticorros|antiferrug|fosfor|pintura|eletrostat"),
    )),
    ("MECANISMOS E ACESSÓRIOS", (
        ("Pistão a gás, quando aplicável", r"pistao.{0,40}gas|gas.{0,40}pistao"),
        ("Diâmetro dos rodízios (mm), quando aplicável", r"rodizio.{0,60}\d+\s*mm|\d+\s*mm.{0,60}rodizio"),
        ("Braços, prancheta e reclinação, quando aplicáveis", r"braco|prancheta|reclin|mecanismo"),
    )),
    ("OBSERVAÇÕES", (
        ("Faixas de regulagem de altura, quando aplicáveis", r"altura.*(?:\ba\b|regul|ajust)|regul.*altura"),
        ("Garantia", r"garantia"),
    )),
)


def evidence_lines(entry):
    lines = list(entry.get("caracteristicas") or [])
    lines.extend(f"{dimension['rotulo']}: {dimension['valores_mm']} mm"
                 for dimension in entry.get("dimensoes", []))
    if entry.get("capacidade_kg") is not None:
        lines.append(f"Capacidade: {entry['capacidade_kg']} kg")
    lines.extend(entry.get("normas") or [])
    return lines


def clause_supported(lines, clause):
    return any(folded(clause) in folded(line)
               and not re.search(r"\bnao\b|pendente|a confirmar|sem comprov", folded(line))
               for line in lines)


def technical_pending_questions(entry):
    lines = evidence_lines(entry)
    evidence = folded("\n".join(lines))
    questions = []
    for title, fields in SECTIONS:
        for label, pattern in fields:
            if not re.search(pattern, evidence):
                questions.append({"titulo": title, "requisito": label,
                                  "contexto": "Informe o dado da configuração ofertada e sua fonte; indique quando não se aplica."})
    for title, clause in STANDARD_CLAUSES:
        if not clause_supported(lines, clause):
            questions.append({"titulo": title, "requisito": f"Confirmar cláusula padrão: {clause}",
                              "contexto": "Não basta constar no edital. Confirme a especificação completa do produto ou informe a diferença/não aplicabilidade."})
    return questions


def technical_sections(entry, characteristics):
    answers = entry.get("respostas_layout") or {}
    sections = []
    used = set()
    for title, fields in SECTIONS:
        lines = []
        if title == "RESUMO DO ITEM":
            lines.extend([f"Item nº: {', '.join(entry.get('itens', [])) or 'A confirmar'}",
                          f"Modelo: {entry['nome']}", "Marca: Goldflex"])
        missing = []
        for label, pattern in fields:
            if answers.get(label):
                lines.append(f"{label}: {answers[label]}")
                continue
            matches = [line for line in characteristics if re.search(pattern, folded(line))]
            if matches:
                lines.extend(matches)
                used.update(matches)
            else:
                missing.append(label)
        if missing:
            lines.append("A confirmar: " + "; ".join(missing) + ".")
        for clause_title, clause in STANDARD_CLAUSES:
            if title != clause_title:
                continue
            if clause_supported(characteristics, clause):
                prefix = "Conformidade declarada na evidência: " if title == "RESUMO DO ITEM" else ""
                lines.append(prefix + clause)
            elif answers.get(f"Confirmar cláusula padrão: {clause}"):
                lines.append("Redação padrão não confirmada: " + clause + ". Informação prestada: "
                             + answers[f"Confirmar cláusula padrão: {clause}"])
            else:
                lines.append("Cláusula padrão pendente de confirmação (não é declaração de atendimento): " + clause)
        sections.append((title, list(dict.fromkeys(lines))))
    # Keep technical evidence that does not fit one of the standardized fields.
    for line in characteristics:
        if line in used:
            continue
        text = folded(line)
        destination = 3 if re.search(r"pistao|rodizio|braco|prancheta|mecanismo|apoio lombar", text) else 4
        sections[destination][1].append(line)
    return sections


def identification_lines(metadata, manufacturer):
    metadata = metadata or {}
    return [
        f"Fabricante: {manufacturer['razao_social']}",
        f"CNPJ: {manufacturer['cnpj']}",
        f"Pregão Eletrônico nº: {metadata.get('numero_compra') or metadata.get('numero_pregao') or 'A confirmar'}",
        f"Processo nº: {metadata.get('processo') or 'A confirmar'}",
        f"Órgão Destinatário: {metadata.get('orgao') or 'A confirmar'}",
    ]
