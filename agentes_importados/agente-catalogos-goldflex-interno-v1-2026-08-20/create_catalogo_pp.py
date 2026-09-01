from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

OUT = Path("dados extraidos") / "catalogo-cadeira-universitaria-pp-prancheta.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)
NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2F75B5")
LIGHT = colors.HexColor("#EAF2F8")
PALE = colors.HexColor("#F6F8FB")
INK = colors.HexColor("#1F2933")
MUTED = colors.HexColor("#667085")

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=27, textColor=NAVY, alignment=TA_CENTER, spaceAfter=5))
styles.add(ParagraphStyle(name="CoverSub", parent=styles["Normal"], fontSize=11.5, leading=15, textColor=MUTED, alignment=TA_CENTER, spaceAfter=13))
styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12.5, leading=14.5, textColor=NAVY, spaceBefore=5, spaceAfter=3))
styles.add(ParagraphStyle(name="Body", parent=styles["BodyText"], fontSize=8.2, leading=10.2, textColor=INK, spaceAfter=2))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.2, leading=8.7, textColor=MUTED, spaceAfter=1))
styles.add(ParagraphStyle(name="Label", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.1, leading=9.8, textColor=NAVY))
styles.add(ParagraphStyle(name="WhiteSmall", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.7, leading=9.3, textColor=colors.white))

def P(text, style="Body"):
    return Paragraph(text, styles[style])

def box(data, widths, header=False, first_col=True):
    commands = [
        ("BOX", (0, 0), (-1, -1), .55, colors.HexColor("#B7C9DB")),
        ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#D9E2F3")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]
    if header:
        commands += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white)]
    elif first_col:
        commands += [("BACKGROUND", (0, 0), (0, -1), LIGHT)]
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    table.setStyle(TableStyle(commands))
    return table

def page_header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(NAVY)
    canvas.rect(0, height - 11 * mm, width, 11 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 7.7)
    canvas.drawString(16 * mm, height - 7.4 * mm, "CATALOGO TECNICO | MODELO DE REFERENCIA")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.2)
    canvas.drawString(16 * mm, 8 * mm, "Cadeira Universitaria Fixa em Polipropileno com Prancheta")
    canvas.drawRightString(width - 16 * mm, 8 * mm, f"Pagina {doc.page} de 2")
    canvas.restoreState()

doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=18 * mm, bottomMargin=12 * mm, title="Catalogo Tecnico - Cadeira Universitaria Fixa em Polipropileno com Prancheta", author="Goldflex")
story = []

# PAGINA 1: identification and commercial/technical overview
story += [Spacer(1, 10 * mm), P("Cadeira Universitaria Fixa", "CoverTitle"), P("em Polipropileno Injetado com Prancheta Fixa", "CoverTitle"), P("Modelo fixo para uso universitario | Configuracao com braco/prancheta fixa", "CoverSub")]
story += [box([[P("MARCA / FABRICANTE", "WhiteSmall"), P("IDENTIFICACAO DO MODELO", "WhiteSmall")], [P("Marca comercial nao identificada no PDF-fonte; fabricante: ALPHERFLEX", "Label"), P("Cadeira Universitaria Fixa em Polipropileno com Prancheta", "Body")]], [75 * mm, 99 * mm], header=True), Spacer(1, 5 * mm)]
story += [P("Apresentacao", "Section"), P("Cadeira universitaria fixa composta por assento e encosto em polipropileno (PP) de alta resistencia, estrutura metalica soldada e prancheta fixa. Esta ficha foi organizada a partir do catalogo analisado e do laudo tecnico do modelo, preservando as medidas de referencia e separando os campos que nao foram evidenciados.")]
story += [P("Fabricante identificado no catalogo analisado", "Small"), P("ALPHERFLEX INDUSTRIA E COMERCIO DE MOVEIS E FERRAGENS LTDA", "Body")]
story += [box([[P("CNPJ", "Label"), P("40.919.354/0001-59")], [P("Endereco", "Label"), P("Avenida Brasil, 2076, Santa Cruz, Mogi Mirim - SP, CEP 13.800-444")], [P("Contato", "Label"), P("(19) 97126-6023 | cadeirasalphaflex@gmail.com")]], [28 * mm, 146 * mm], first_col=True), Spacer(1, 3 * mm)]
story += [P("Classificacao do produto", "Section"), box([[P("Categoria", "Label"), P("Cadeiras em polipropileno injetado")], [P("Tipo construtivo", "Label"), P("Cadeira fixa universitaria")], [P("Apoio lateral", "Label"), P("Braco/prancheta fixa")], [P("Assento e encosto", "Label"), P("Polipropileno (PP) de alta resistencia")], [P("Uso documental", "Label"), P("Modelo de referencia aprovado/travado; medidas do catalogo nao devem ser alteradas")]], [45 * mm, 129 * mm])]
story += [P("Dimensoes de referencia", "Section"), box([[P("Componente", "WhiteSmall"), P("Medida aproximada", "WhiteSmall"), P("Ordem da medida", "WhiteSmall")], [P("Assento", "Label"), P("42 cm profundidade x 46 cm largura"), P("Profundidade x largura")], [P("Encosto", "Label"), P("28,0 cm altura x 46 cm largura"), P("Altura x largura")], [P("Prancheta", "Label"), P("49 cm profundidade x 23 cm largura x 1,8 cm espessura"), P("Profundidade x largura x espessura")]], [37 * mm, 83 * mm, 54 * mm], header=True)]
story += [P("As medidas acima sao aproximadas e reproduzem a referencia registrada na analise. Altura total, altura do assento e largura total nao foram evidenciadas no catalogo analisado.", "Small")]
story += [P("Destaques tecnicos", "Section"), box([[P("Material estrutural", "Label"), P("Aco carbono com tratamento antiferrugem e pintura a po eletrostatica")], [P("Montagem", "Label"), P("Componentes unidos por solda MIG")], [P("Prancheta", "Label"), P("MDP/MDF entre 18 mm, laminado melaminico nas duas faces e acabamento em fita PVC")], [P("Apoio de livros", "Label"), P("Porta-livros mencionado na referencia; detalhes dimensionais e material nao informados")]], [42 * mm, 132 * mm])]
story += [P("Referencia de evidencia: catalogo UFRGS de cadeira fixa em polipropileno com prancheta, p. 1; laudo-final-modelos-ufrgs.md, modelo 1.", "Small"), PageBreak()]

# PAGINA 2: construction, finishes, evidence and control
story += [P("Especificacao construtiva", "Section"), box([[P("Elemento", "WhiteSmall"), P("Descricao tecnica evidenciada", "WhiteSmall")], [P("Suportes do encosto", "Label"), P("Dois tubos oblongos de aco carbono, secao 16 x 30 mm, espessura 1,5 mm.")], [P("Suportes do assento", "Label"), P("Dois tubos redondos, secao 3/4, espessura 1,2 mm.")], [P("Pes", "Label"), P("Dois tubos oblongos, secao 16 x 30 mm, espessura 1,2 mm.")], [P("Uniao", "Label"), P("Solda MIG, conforme descricao do catalogo analisado.")], [P("Ponteiras/deslizantes", "Label"), P("Acabamentos deslizantes nos pes; tipo e composicao detalhados nao informados.")]], [44 * mm, 130 * mm], header=True)]
story += [P("Tratamento e acabamento", "Section"), box([[P("Etapa", "WhiteSmall"), P("Informacao registrada", "WhiteSmall")], [P("Preparacao", "Label"), P("Desengraxe, estabilizacao e fosforizacao.")], [P("Protecao", "Label"), P("Tratamento antiferrugem.")], [P("Pintura", "Label"), P("Pintura a po eletrostatica.")], [P("Cura", "Label"), P("Secagem em estufa a 250 graus C.")], [P("Cores", "Label"), P("Nao informadas no catalogo analisado; confirmar na configuracao ofertada.")]], [44 * mm, 130 * mm], header=True)]
story += [P("Prancheta e ergonomia de uso", "Section"), P("A prancheta fixa e descrita como MDP/MDF entre 18 mm, revestida com laminado melaminico nas duas faces e com fita PVC. A medida de referencia registrada e aproximadamente 49 x 23 x 1,8 cm. O catalogo menciona porta-livros, mas nao detalha suas dimensoes, material, fixacao ou capacidade.")]
story += [P("Controle documental e campos a confirmar", "Section"), box([[P("Campo", "WhiteSmall"), P("Situacao no material analisado", "WhiteSmall")], [P("Codigo comercial", "Label"), P("Nao informado; atribuir somente em ficha interna/proposta.")], [P("Altura total, altura do assento e largura total", "Label"), P("Nao evidenciadas; medir e registrar na configuracao ofertada.")], [P("Capacidade de carga e norma", "Label"), P("Nao informadas neste catalogo; anexar laudos/ensaios quando exigidos no edital.")], [P("Cores, garantia e embalagem", "Label"), P("Nao informadas; confirmar comercialmente e na ficha tecnica.")], [P("Canhoto/destro", "Label"), P("Nao informado para este modelo PP; confirmar possibilidade de configuracao.")]], [63 * mm, 111 * mm], header=True)]
story += [P("Orientacao para proposta", "Section"), P("Usar este PDF como referencia de modelo e seguranca comercial. Para cada edital, apresentar separadamente a configuracao ofertada, medidas efetivamente produzidas, materiais, acabamentos, desenhos, amostra e o pacote de laudos/ensaios solicitado. Medidas maiores ou variacoes de tecido/acabamento devem ser tratadas como configuracao a confirmar, sem modificar este catalogo-base.")]
story += [P("Nota de evidencia", "Section"), P("Este documento nao acrescenta cores, capacidade, normas, garantia, dimensoes globais ou outras especificacoes ausentes da fonte. Informacoes de aprovacao historica sao premissas fornecidas pela empresa e nao equivalem a certificados revisados nesta pasta.", "Small")]

doc.build(story, onFirstPage=page_header_footer, onLaterPages=page_header_footer)
print(OUT.resolve())
