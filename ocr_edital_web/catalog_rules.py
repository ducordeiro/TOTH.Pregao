import copy
import re
import unicodedata


CATALOG_POLICY = {
    "version": "goldflex-v4.0",
    "architecture": "catalogo_generico_com_auditoria_separada",
    "page_size": "A4",
    "orientation": "retrato",
    "brand_color": "#FFC000",
    "section_title": "Características",
    "manufacturer": (
        "GOLDFLEX INDUSTRIA E COMERCIO DE MOVEIS E EQUIPAMENTOS LTDA "
        "CNPJ 33.661.439/0001-14"
    ),
    "rules": [
        "Gerar um catálogo genérico por modelo, sem adaptar o catálogo ao edital.",
        "Publicar somente características sustentadas pelo repertório técnico.",
        "Manter a comparação com a oportunidade em relatório de auditoria separado.",
        "Não inferir medidas, materiais, cores, normas, capacidade ou configuração.",
        "Aplicar tolerância somente quando ela estiver expressamente autorizada no processo.",
        "Bloquear a liberação quando houver conflito ou modelo sem evidência suficiente.",
        "Exigir revisão humana antes da liberação comercial.",
    ],
    "evidence_states": [
        "comprovado_no_catalogo",
        "comprovado_no_laudo",
        "confirmado_pelo_fabricante",
        "configuracao_a_confirmar",
        "nao_evidenciado",
        "conflitante",
    ],
}

REPERTOIRE_SOURCE = (
    "agentes_importados/agente-catalogos-goldflex-interno-v1-2026-08-20/"
    "analises/registro-modelos-aprovados.md"
)


MODEL_PROFILES = (
    {
        "id": "ufrgs-pp-prancheta",
        "name": "Cadeira universitária fixa em PP com prancheta",
        "family": "Cadeira universitária fixa",
        "technical_level": "intermediário",
        "movement": "fixa",
        "signals": (
            ("universitaria", 1.2), ("prancheta", 2.5), ("polipropileno", 4.0),
            ("assento em pp", 4.0), ("encosto em pp", 4.0), ("deslizantes", 2.0),
            ("solda mig", 1.2), ("fixa", 0.8),
        ),
        "specific_signals": ("prancheta", "polipropileno", "assento em pp", "encosto em pp"),
        "capabilities": {
            "prancheta", "polipropileno", "solda_mig", "deslizantes", "estrutura_aco"
        },
        "characteristics": (
            "Cadeira universitária de estrutura fixa com prancheta.",
            "Assento e encosto em polipropileno.",
            "Estrutura em aço com solda MIG.",
            "Apoios deslizantes na estrutura.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura)", "axes": ("altura", "largura"), "values_mm": (280.0, 460.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura)", "axes": ("profundidade", "largura"), "values_mm": (420.0, 460.0), "approximate": True},
            {"part": "prancheta", "label": "Prancheta (comprimento x largura x espessura)", "axes": ("comprimento", "largura", "espessura"), "values_mm": (490.0, 230.0, 18.0), "approximate": True},
        ),
        "capacity_kg": None,
        "norms": (),
        "pending": (
            "Código comercial do modelo.", "Capacidade de carga.", "Norma e laudos aplicáveis.",
            "Furos de aeração e versão para canhoto.",
        ),
        "source": "Catálogo aprovado UFRGS — PP com prancheta",
    },
    {
        "id": "ufrgs-estofada-prancheta",
        "name": "Cadeira universitária fixa estofada com prancheta",
        "family": "Cadeira universitária fixa",
        "technical_level": "completo com pendências",
        "movement": "fixa",
        "signals": (
            ("universitaria", 1.2), ("prancheta", 2.5), ("estofada", 1.8),
            ("poliester", 2.5), ("compensado", 2.2), ("130 kg", 4.0),
            ("nbr 16671", 4.0), ("canhoto", 2.5), ("destro", 1.5), ("fixa", 0.8),
        ),
        "specific_signals": ("prancheta", "130 kg", "nbr 16671", "canhoto", "poliester"),
        "capabilities": {
            "prancheta", "estofada", "compensado", "espuma_pu", "poliester", "destro_canhoto"
        },
        "characteristics": (
            "Cadeira universitária de estrutura fixa com prancheta.",
            "Assento e encosto em compensado multilaminado com espessura mínima declarada de 12 mm.",
            "Espuma de poliuretano com densidade mínima declarada de 50 kg/m³.",
            "Revestimento em tecido 100% poliéster.",
            "Configurações declaradas para destro e canhoto.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura x espessura)", "axes": ("altura", "largura", "espessura"), "values_mm": (290.0, 360.0, 40.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura x espessura)", "axes": ("profundidade", "largura", "espessura"), "values_mm": (390.0, 420.0, 50.0), "approximate": True},
            {"part": "prancheta", "label": "Prancheta (comprimento x largura x espessura)", "axes": ("comprimento", "largura", "espessura"), "values_mm": (490.0, 230.0, 18.0), "approximate": True},
        ),
        "capacity_kg": 130.0,
        "norms": ("ABNT NBR 16671:2018",),
        "pending": (
            "Confirmar se a espuma é moldada ou injetada.", "Cores ofertáveis.",
            "Código comercial e dimensões globais.",
        ),
        "source": "Catálogo aprovado UFRGS — estofada com prancheta",
    },
    {
        "id": "pinhais-giratoria-tela",
        "name": "Cadeira de escritório giratória em tela",
        "family": "Cadeira de escritório giratória",
        "technical_level": "completo com pendências",
        "movement": "giratória",
        "signals": (
            ("giratoria", 1.8), ("tela", 3.5), ("mesh", 4.0),
            ("apoio lombar", 1.8), ("back system", 3.5), ("pistao classe 4", 4.0),
            ("cinco rodizios", 2.5), ("rodizios", 1.0), ("6 regulagens", 3.5),
        ),
        "specific_signals": ("tela", "mesh", "back system", "pistao classe 4", "6 regulagens"),
        "capabilities": {
            "giratoria", "tela", "apoio_lombar", "back_system", "pistao_classe_4",
            "rodizios", "bracos_regulaveis"
        },
        "characteristics": (
            "Cadeira de escritório giratória com encosto em tela Mesh.",
            "Apoio lombar descrito na referência.",
            "Mecanismo Back System.",
            "Pistão classe 4 e base com cinco rodízios.",
            "Braços com seis regulagens descritas.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura x espessura)", "axes": ("altura", "largura", "espessura"), "values_mm": (540.0, 450.0, 80.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura x espessura)", "axes": ("profundidade", "largura", "espessura"), "values_mm": (480.0, 490.0, 80.0), "approximate": True},
            {"part": "altura_assento", "label": "Faixa de altura do assento", "axes": ("mínima", "máxima"), "values_mm": (455.0, 565.0), "approximate": False},
            {"part": "altura_total", "label": "Faixa de altura global informada", "axes": ("mínima", "máxima"), "values_mm": (980.0, 1090.0), "approximate": False},
        ),
        "capacity_kg": None,
        "norms": (),
        "pending": (
            "Relação exata entre tela e revestimento em courvin.",
            "Código comercial e conjunto documental completo.",
        ),
        "source": "Catálogo aprovado Pinhais — cadeira em tela",
    },
    {
        "id": "creci-giratoria-ergonomica",
        "name": "Cadeira de escritório giratória ergonômica com braços",
        "family": "Cadeira de escritório giratória",
        "technical_level": "completo com pendências",
        "movement": "giratória",
        "signals": (
            ("ergonomica", 2.5), ("giratoria", 1.5), ("apoio lombar", 1.5),
            ("back system", 2.5), ("7 posicoes", 4.0), ("75 mm", 2.0),
            ("135 kg", 4.5), ("d55", 4.0), ("d-55", 4.0),
        ),
        "specific_signals": ("ergonomica", "7 posicoes", "135 kg", "d55", "d-55"),
        "capabilities": {"giratoria", "ergonomica", "apoio_lombar", "back_system", "bracos", "espuma_d55"},
        "characteristics": (
            "Cadeira de escritório giratória ergonômica com braços.",
            "Apoio lombar descrito na referência.",
            "Mecanismo Back System com sete posições e curso declarado de 75 mm.",
            "Espuma com densidade declarada D55.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura)", "axes": ("altura", "largura"), "values_mm": (470.0, 440.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura)", "axes": ("profundidade", "largura"), "values_mm": (460.0, 480.0), "approximate": True},
            {"part": "altura_assento", "label": "Faixa de altura do assento", "axes": ("mínima", "máxima"), "values_mm": (420.0, 540.0), "approximate": False},
        ),
        "capacity_kg": 135.0,
        "norms": (),
        "pending": (
            "Garantia e embalagem.", "Coluna e detalhes construtivos dos braços.",
            "Normas e laudos aplicáveis.",
        ),
        "source": "Catálogo aprovado CRECI — ergonômica com braços",
    },
    {
        "id": "bh-fixa-estofada",
        "name": "Cadeira fixa estofada",
        "family": "Cadeira fixa",
        "technical_level": "intermediário",
        "movement": "fixa",
        "signals": (
            ("cadeira fixa", 1.3), ("estofada", 1.5), ("couro ecologico", 3.5),
            ("tubo 7/8", 3.5), ("sapatas de borracha", 2.5),
            ("pintura eletrostatica", 2.5), ("solda mig", 1.2),
        ),
        "specific_signals": ("couro ecologico", "tubo 7/8", "sapatas de borracha", "pintura eletrostatica"),
        "capabilities": {"fixa", "estofada", "couro_ecologico", "solda_mig", "sapatas_borracha", "pintura_eletrostatica"},
        "characteristics": (
            "Cadeira de estrutura fixa com assento e encosto estofados.",
            "Componentes anatômicos em madeira.",
            "Revestimento em couro ecológico preto.",
            "Estrutura em tubo 7/8 com reforço de 25 cm e solda MIG.",
            "Sapatas de borracha e pintura eletrostática.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura)", "axes": ("altura", "largura"), "values_mm": (270.0, 390.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura)", "axes": ("profundidade", "largura"), "values_mm": (420.0, 430.0), "approximate": True},
        ),
        "capacity_kg": None,
        "norms": (),
        "pending": (
            "Espuma e capacidade de carga.", "Laudos aplicáveis.",
            "Fixação por quatro parafusos e acabamento epóxi preto-fosco.",
        ),
        "source": "Catálogo aprovado BH — Fixa Estofada",
    },
    {
        "id": "bh-universitaria-executiva",
        "name": "Cadeira universitária executiva com braço escamoteável",
        "family": "Cadeira universitária fixa",
        "technical_level": "intermediário",
        "movement": "fixa",
        "signals": (
            ("universitaria", 1.0), ("executiva", 2.2), ("braco escamoteavel", 5.0),
            ("bracos escamoteaveis", 5.0), ("suporte para livros", 4.0),
            ("couro sintetico", 2.5), ("tubo 7/8", 2.0),
        ),
        "specific_signals": ("executiva", "braco escamoteavel", "bracos escamoteaveis", "suporte para livros"),
        "capabilities": {"fixa", "universitaria", "estofada", "couro_sintetico", "bracos_escamoteaveis", "suporte_livros"},
        "characteristics": (
            "Cadeira universitária executiva de estrutura fixa.",
            "Assento e encosto anatômicos em madeira com revestimento em couro sintético preto.",
            "Braços escamoteáveis.",
            "Suporte para livros descrito na referência.",
            "Estrutura em tubo 7/8.",
        ),
        "dimensions": (
            {"part": "encosto", "label": "Encosto (altura x largura)", "axes": ("altura", "largura"), "values_mm": (370.0, 420.0), "approximate": True},
            {"part": "assento", "label": "Assento (profundidade x largura)", "axes": ("profundidade", "largura"), "values_mm": (435.0, 460.0), "approximate": True},
        ),
        "capacity_kg": None,
        "norms": (),
        "pending": (
            "Aplicabilidade quando a oportunidade solicitar versão sem braço.",
            "Dimensões globais, laudos e capacidade de carga.",
        ),
        "source": "Catálogo aprovado BH — Executiva com braço escamoteável",
    },
)


FEATURE_REQUIREMENTS = (
    ("prancheta", ("prancheta",), "Prancheta"),
    ("polipropileno", ("polipropileno", "assento em pp", "encosto em pp"), "Polipropileno"),
    ("tela", ("tela mesh", "encosto em tela", "tela"), "Encosto em tela"),
    ("apoio_lombar", ("apoio lombar", "suporte lombar"), "Apoio lombar"),
    ("back_system", ("back system", "backsystem"), "Mecanismo Back System"),
    ("pistao_classe_4", ("pistao classe 4",), "Pistão classe 4"),
    ("rodizios", ("rodizios",), "Rodízios"),
    ("bracos_regulaveis", ("bracos regulaveis", "braco regulavel"), "Braços reguláveis"),
    ("bracos_escamoteaveis", ("bracos escamoteaveis", "braco escamoteavel"), "Braços escamoteáveis"),
    ("suporte_livros", ("suporte para livros", "porta livros"), "Suporte para livros"),
    ("solda_mig", ("solda mig",), "Solda MIG"),
    ("pintura_eletrostatica", ("pintura eletrostatica",), "Pintura eletrostática"),
    ("espuma_d55", ("espuma d55", "espuma d-55", "densidade d55"), "Espuma D55"),
)


def normalize_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text).strip().lower()


def item_requirement_text(item):
    return " ".join(
        str(item.get(field) or "")
        for field in (
            "produto", "descricao", "especificacao_tecnica", "criterios_aceitacao",
            "observacoes", "categoria", "subcategoria",
        )
    )


def public_profile(profile):
    return {
        "id": profile["id"],
        "nome": profile["name"],
        "familia": profile["family"],
        "nivel_tecnico": profile["technical_level"],
        "fonte": profile["source"],
        "caracteristicas": list(profile["characteristics"]),
        "dimensoes": [
            {
                "parte": dimension["part"],
                "rotulo": dimension["label"],
                "eixos": list(dimension["axes"]),
                "valores_mm": list(dimension["values_mm"]),
                "aproximada": dimension["approximate"],
            }
            for dimension in profile["dimensions"]
        ],
        "capacidade_kg": profile["capacity_kg"],
        "normas": list(profile["norms"]),
        "pendencias": list(profile["pending"]),
    }


def catalog_policy_summary():
    return copy.deepcopy(CATALOG_POLICY)


def repertoire_summary():
    return {
        "structured_models": len(MODEL_PROFILES),
        "source_documents": 47,
        "source": REPERTOIRE_SOURCE,
        "scope_note": (
            "Seis perfis possuem consolidação estruturada. Os demais documentos do agente "
            "permanecem como biblioteca de evidências e não autorizam alegações automáticas."
        ),
        "models": [
            {
                "id": profile["id"],
                "nome": profile["name"],
                "familia": profile["family"],
                "fonte": profile["source"],
            }
            for profile in MODEL_PROFILES
        ],
    }


def match_model(item):
    text = normalize_text(item_requirement_text(item))
    if not any(term in text for term in ("cadeira", "assento", "poltrona")):
        return None, None

    ranked = []
    for profile in MODEL_PROFILES:
        matches = [(term, weight) for term, weight in profile["signals"] if term in text]
        matched_terms = {term for term, _ in matches}
        if not any(term in matched_terms for term in profile["specific_signals"]):
            continue
        score = sum(weight for _, weight in matches)
        if profile["movement"] == "fixa" and "giratoria" in text:
            score -= 4.0
        if profile["movement"] == "giratória" and "cadeira fixa" in text:
            score -= 4.0
        ranked.append((score, len(matches), profile, sorted(matched_terms)))

    if not ranked:
        return None, None
    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    score, _count, profile, matched_terms = ranked[0]
    if score < 4.0:
        return None, None
    confidence = "alta" if score >= 8.0 else "média" if score >= 5.5 else "baixa"
    reference = {
        "id": profile["id"],
        "nome": profile["name"],
        "familia": profile["family"],
        "confianca": confidence,
        "pontuacao": round(min(score / 12.0, 1.0), 3),
        "sinais_encontrados": matched_terms,
        "fonte": profile["source"],
    }
    return profile, reference


def criterion(identifier, label, requirement, state, evidence, **details):
    result = {
        "id": identifier,
        "criterio": label,
        "requisito": requirement,
        "estado": state,
        "evidencia_repertorio": evidence,
    }
    result.update(details)
    return result


def movement_criteria(text, profile):
    checks = []
    for expected, pattern in (("giratória", "giratoria"), ("fixa", "cadeira fixa")):
        if pattern not in text:
            continue
        matches = profile["movement"] == expected
        checks.append(criterion(
            f"movimento_{normalize_text(expected)}",
            "Tipo de movimento",
            expected,
            "evidenciado_na_referencia" if matches else "divergente",
            profile["movement"],
        ))
    return checks


def feature_criteria(text, profile):
    checks = []
    capabilities = profile["capabilities"]
    for identifier, patterns, label in FEATURE_REQUIREMENTS:
        matched = next((pattern for pattern in patterns if pattern in text), None)
        if not matched:
            continue
        evidenced = identifier in capabilities
        checks.append(criterion(
            identifier,
            label,
            matched,
            "evidenciado_na_referencia" if evidenced else "nao_evidenciado",
            label if evidenced else "Sem evidência neste perfil",
        ))
    return checks


def capacity_criteria(text, profile):
    matches = re.findall(
        r"(?:capacidade|carga|suporta(?:r)?|até|ate)?[^.;]{0,28}?\b(\d{2,3}(?:[.,]\d+)?)\s*kg\b",
        text,
    )
    if not matches:
        return []
    required = max(float(value.replace(",", ".")) for value in matches)
    available = profile["capacity_kg"]
    if available is None:
        return [criterion(
            "capacidade_carga", "Capacidade de carga", f"{required:g} kg",
            "nao_evidenciado", "Capacidade não consolidada para este perfil",
        )]
    difference = available - required
    state = "potencialmente_atende" if difference >= 0 else "divergente"
    return [criterion(
        "capacidade_carga", "Capacidade de carga", f"{required:g} kg", state,
        f"{available:g} kg declarados no repertório",
        diferenca_absoluta_kg=round(difference, 3),
        diferenca_percentual=round((difference / required) * 100, 3) if required else None,
        declaracao_atendimento_automatica=False,
    )]


def norm_criteria(text, profile):
    requested = re.findall(r"(?:abnt\s+)?nbr\s*[0-9.]+(?:\s*[:/]\s*\d{4})?", text)
    profile_norms = list(profile["norms"])
    normalized_norms = [normalize_text(value) for value in profile_norms]
    checks = []
    for value in dict.fromkeys(requested):
        number = re.search(r"\d{4,}", value.replace(".", ""))
        evidenced = bool(number and any(number.group(0) in norm.replace(".", "") for norm in normalized_norms))
        checks.append(criterion(
            f"norma_{normalize_text(value).replace(' ', '_')}", "Norma técnica", value.upper(),
            "evidenciado_na_referencia" if evidenced else "nao_evidenciado",
            ", ".join(profile_norms) if evidenced else "Norma não consolidada para este perfil",
        ))
    return checks


def to_millimetres(value, unit):
    number = float(value.replace(",", "."))
    return number * 10.0 if unit == "cm" else number


def parsed_dimensions(text):
    results = []
    seen = set()
    compound = re.compile(
        r"\b(encosto|assento|prancheta)\b(?P<context>[^.;\n]{0,80}?)"
        r"(?P<values>\d+(?:[.,]\d+)?(?:\s*[x×]\s*\d+(?:[.,]\d+)?){1,2})\s*(?P<unit>mm|cm)\b"
    )
    for match in compound.finditer(text):
        values = re.split(r"\s*[x×]\s*", match.group("values"))
        parsed = {
            "part": match.group(1),
            "axes": None,
            "values_mm": [to_millimetres(value, match.group("unit")) for value in values],
            "raw": match.group(0).strip(),
            "context": match.group("context"),
        }
        key = (parsed["part"], None, tuple(parsed["values_mm"]))
        if key not in seen:
            seen.add(key)
            results.append(parsed)
    single = re.compile(
        r"\b(encosto|assento|prancheta)\b(?P<context>[^.;\n]{0,60}?)"
        r"\b(largura|altura|profundidade|espessura|comprimento)\b[^0-9]{0,18}"
        r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>mm|cm)\b"
    )
    for match in single.finditer(text):
        raw = match.group(0).strip()
        if any(raw in existing["raw"] for existing in results):
            continue
        parsed = {
            "part": match.group(1),
            "axes": [match.group(3)],
            "values_mm": [to_millimetres(match.group("value"), match.group("unit"))],
            "raw": raw,
            "context": match.group("context"),
        }
        key = (parsed["part"], tuple(parsed["axes"]), tuple(parsed["values_mm"]))
        if key not in seen:
            seen.add(key)
            results.append(parsed)
    return results


def dimension_criteria(text, profile):
    checks = []
    profile_dimensions = profile["dimensions"]
    tolerance_authorized = bool(re.search(r"tolerancia[^.;]{0,20}5\s*%|[±+]\s*5\s*%", text))
    for index, requested in enumerate(parsed_dimensions(text)):
        candidates = [value for value in profile_dimensions if value["part"] == requested["part"]]
        if requested["axes"]:
            candidates = [
                value for value in candidates
                if all(axis in value["axes"] for axis in requested["axes"])
            ]
        candidate = next((value for value in candidates if len(value["values_mm"]) == len(requested["values_mm"])), None)
        if candidate is None and requested["axes"] and candidates:
            value = candidates[0]
            available = [value["values_mm"][value["axes"].index(axis)] for axis in requested["axes"]]
            candidate = dict(value, values_mm=tuple(available), axes=tuple(requested["axes"]))
        if candidate is None:
            checks.append(criterion(
                f"dimensao_{requested['part']}_{index}", "Dimensão", requested["raw"],
                "nao_evidenciado", "Eixos ou medida equivalentes não consolidados no perfil",
            ))
            continue

        differences = [
            round(available - required, 3)
            for available, required in zip(candidate["values_mm"], requested["values_mm"])
        ]
        percentages = [
            round((difference / required) * 100, 3) if required else None
            for difference, required in zip(differences, requested["values_mm"])
        ]
        context = requested["context"]
        is_minimum = "minim" in context
        is_maximum = "maxim" in context
        exact = all(abs(difference) <= 0.5 for difference in differences)
        if exact:
            state = "evidenciado_na_referencia"
        elif is_minimum and all(difference >= 0 for difference in differences):
            state = "potencialmente_atende"
        elif is_maximum and all(difference <= 0 for difference in differences):
            state = "potencialmente_atende"
        elif is_minimum and any(difference < 0 for difference in differences):
            within_tolerance = tolerance_authorized and all(
                percentage is not None and percentage >= -5.0 for percentage in percentages
            )
            state = "compatibilidade_a_confirmar" if within_tolerance else "divergente"
        elif is_maximum and any(difference > 0 for difference in differences):
            within_tolerance = tolerance_authorized and all(
                percentage is not None and percentage <= 5.0 for percentage in percentages
            )
            state = "compatibilidade_a_confirmar" if within_tolerance else "divergente"
        else:
            state = "compatibilidade_a_confirmar"
        checks.append(criterion(
            f"dimensao_{requested['part']}_{index}", "Dimensão", requested["raw"], state,
            candidate["label"],
            valores_requeridos_mm=requested["values_mm"],
            valores_repertorio_mm=list(candidate["values_mm"]),
            eixos=list(candidate["axes"]),
            diferencas_absolutas_mm=differences,
            diferencas_percentuais=percentages,
            tolerancia_percentual=5 if tolerance_authorized else None,
            tolerancia_expressamente_autorizada=tolerance_authorized,
            declaracao_atendimento_automatica=False,
        ))
    return checks


def unique_strings(values):
    return list(dict.fromkeys(value for value in values if value))


def analyze_catalog_item(item):
    analyzed = dict(item)
    text = normalize_text(item_requirement_text(analyzed))
    profile, reference = match_model(analyzed)
    analyzed["modelo_referencia"] = reference
    analyzed["analise_desatualizada"] = False
    if profile is None:
        analyzed["caracteristicas_catalogo"] = []
        analyzed["analise_aderencia"] = {
            "resultado": "sem_modelo_correspondente",
            "criterios": [],
            "pendencias": [
                "Nenhum dos seis perfis estruturados apresentou evidência suficiente para este item.",
                "Identificar o modelo e anexar evidências antes de publicar características técnicas.",
            ],
            "revisao_humana_obrigatoria": True,
            "declaracao_atendimento_automatica": False,
        }
        analyzed["status_catalogo"] = "bloqueado_sem_modelo"
        return analyzed

    criteria = []
    criteria.extend(movement_criteria(text, profile))
    criteria.extend(feature_criteria(text, profile))
    criteria.extend(capacity_criteria(text, profile))
    criteria.extend(norm_criteria(text, profile))
    criteria.extend(dimension_criteria(text, profile))
    missing = [
        f"{entry['criterio']}: {entry['requisito']} não está evidenciado no perfil selecionado."
        for entry in criteria
        if entry["estado"] == "nao_evidenciado"
    ]
    conflicts = [entry for entry in criteria if entry["estado"] == "divergente"]
    confirm = [
        entry for entry in criteria
        if entry["estado"] in {"potencialmente_atende", "compatibilidade_a_confirmar"}
    ]
    pending = unique_strings(list(profile["pending"]) + missing + [
        f"Confirmar tecnicamente: {entry['criterio']} ({entry['requisito']})."
        for entry in confirm
    ])
    if conflicts:
        result = "revisao_obrigatoria"
        status = "bloqueado_por_divergencia"
    elif pending:
        result = "referencia_identificada_com_pendencias"
        status = "rascunho_para_revisao"
    else:
        result = "referencia_identificada"
        status = "rascunho_para_revisao"
    analyzed["caracteristicas_catalogo"] = list(profile["characteristics"])
    analyzed["analise_aderencia"] = {
        "resultado": result,
        "criterios": criteria,
        "pendencias": pending,
        "revisao_humana_obrigatoria": True,
        "declaracao_atendimento_automatica": False,
    }
    analyzed["status_catalogo"] = status
    return analyzed


def build_catalog_entries(items):
    model_ids = []
    for item in items:
        reference = item.get("modelo_referencia") or {}
        model_id = reference.get("id")
        if model_id and model_id not in model_ids:
            model_ids.append(model_id)
    profiles = {profile["id"]: profile for profile in MODEL_PROFILES}
    return [public_profile(profiles[model_id]) for model_id in model_ids if model_id in profiles]


def catalog_summary(items):
    items = list(items or [])
    matched = sum(bool(item.get("modelo_referencia")) for item in items)
    divergent = sum(item.get("status_catalogo") == "bloqueado_por_divergencia" for item in items)
    unmatched = sum(item.get("status_catalogo") == "bloqueado_sem_modelo" for item in items)
    models = len(build_catalog_entries(items))
    if not items or unmatched == len(items):
        release = "bloqueado_sem_modelo"
    elif divergent or unmatched:
        release = "bloqueado_com_pendencias"
    else:
        release = "pronto_para_revisao_humana"
    return {
        "items_analisados": len(items),
        "items_com_modelo": matched,
        "items_sem_modelo": unmatched,
        "items_com_divergencia": divergent,
        "modelos_catalogados": models,
        "status_liberacao": release,
        "revisao_humana_obrigatoria": True,
    }
