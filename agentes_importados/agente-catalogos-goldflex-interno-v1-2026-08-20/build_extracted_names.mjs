import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";
const out = String.raw`Modelos de catalogos\catalogos de pedidos\dados extraidos`;
const rows = [
  ["Tipo", "Categoria construtiva", "Braços", "Modelo", "Medidas do assento", "Medidas do encosto", "Fonte / registro", "Observações de evidência"],
  ["Fixa", "Cadeiras em polipropileno injetado", "Braço/prancheta fixa", "Cadeira Universitária Fixa em Polipropileno com Prancheta", "aprox. 42 cm profundidade x 46 cm largura", "aprox. 28,0 cm altura x 46 cm largura"],
  ["Fixa", "Cadeiras estofadas", "Braço/prancheta fixa", "Cadeira Universitária Fixa Estofada com Prancheta", "aprox. 39 cm profundidade x 42 cm largura x 5 cm espessura", "aprox. 29 cm altura x 36 cm largura x 4 cm espessura"],
  ["Fixa", "Cadeiras estofadas", "Sem braços", "Modelo Fixa Estofada", "aprox. 42 cm profundidade x 43 cm largura", "aprox. 27 cm altura x 39 cm largura"],
  ["Fixa", "Cadeiras estofadas", "Com braços", "Cadeira Fixa Universitária Executiva Com Braço Escamoteavel", "aprox. 43,5 cm profundidade x 46 cm largura", "aprox. 37 cm altura x 42 cm largura"],
  ["Giratória", "Cadeiras com encosto em tela e assento estofado", "Com braços", "Cadeira Ergonômica Tela Com braços", "aprox. 48 cm profundidade x 49 cm largura x 8 cm espessura", "aprox. 54 cm altura x 45 cm largura x 8 cm espessura"],
  ["Giratória", "Cadeiras estofadas", "Com braços", "Cadeira Ergonômica Com Braços", "aprox. 46 cm profundidade x 48 cm largura", "aprox. 47 cm altura x 44 cm largura"],
  ["Giratória", "Cadeiras com encosto em tela e assento estofado", "Com braços", "Modelo Tela Ergonômica Relax com Braço", "aprox. 48 cm profundidade x 48 cm largura", "aprox. 56 cm altura x 48 cm largura"],
  ["Rebatível", "Cadeiras de auditório estofadas", "Com braços / prancheta escamoteável", "Cadeira de Auditório Rebatível com Braço e Prancheta Escamoteável", "aprox. 48 cm profundidade x 49 cm largura", "aprox. 48 cm altura x 46 cm largura", "Almirante Alexandrino", "Catálogo comprova modelo individual; longarina não evidenciada"],
  ["Fixa", "Cadeiras estofadas", "Não evidenciado", "Item 6 — Cadeira Secretaria Fixa", "aprox. 39 cm profundidade x 42 cm largura", "aprox. 29 cm altura x 37 cm largura", "Patrocínio Paulista", "Braços não descritos no catálogo"],
  ["Giratória", "Cadeiras estofadas", "Com braços", "Item 8 — Cadeira Executiva Lâmina Ergonômica", "aprox. 42 cm profundidade x 46 cm largura", "aprox. 37 cm altura x 40 cm largura", "Patrocínio Paulista", "Altura do assento aprox. 45–56 cm"],
  ["Fixa", "Cadeiras estofadas", "Não evidenciado", "Item 10 — Cadeira Fixa", "aprox. 39 cm profundidade x 42 cm largura", "aprox. 29 cm altura x 37 cm largura", "Patrocínio Paulista", "Braços não descritos no catálogo"],
  ["Giratória", "Bancos/cadeiras semi-sentados em PU", "Não evidenciado", "Item 2 — Banco Semi Sentado com Rodízios", "largura 35 cm x profundidade 28,5 cm", "altura 13 cm x largura 22 cm", "Material Bélico Injetado", "Altura catalogada apresenta ordem inconsistente; confirmar"],
  ["Giratória", "Cadeiras em poliuretano integral skin", "Não evidenciado", "Item 3 — Cadeira Injetada Industrial", "aprox. 41,5 cm profundidade x 43 cm largura x 4 cm espessura", "aprox. 25 cm altura x 40,5 cm largura x 4 cm espessura", "Material Bélico Injetado", "Altura mínima/máxima catalogada: 51–62 cm"],
  ["Fixa", "Cadeiras em polipropileno injetado", "Não evidenciado", "Item 1 — Cadeira Fixa Empilhável", "aprox. 43 cm profundidade x 45 cm largura", "aprox. 30 cm altura x 45 cm largura", "Assistência Jurídica", "Catálogo não explicita concha dupla ou ausência de braços"],
];
await fs.mkdir(out, { recursive: true });
const workbook = Workbook.create(); const sheet = workbook.worksheets.add("Modelos"); sheet.showGridLines = false;
rows[1][6] = "UFRGS"; rows[1][7] = "Medidas aproximadas evidenciadas";
rows[2][6] = "UFRGS"; rows[2][7] = "Medidas aproximadas evidenciadas";
rows[3][6] = "Prefeitura BH"; rows[3][7] = "Sem braços; laudo registra campos ausentes";
rows[4][6] = "Prefeitura BH universitária"; rows[4][7] = "Braço escamoteável; configuração específica";
rows[5][6] = "São José dos Pinhais"; rows[5][7] = "Encosto em tela; medidas aproximadas";
rows[6][6] = "CRECI"; rows[6][7] = "Encosto regulável; medidas aproximadas";
rows[7][6] = "Material Bélico Tela"; rows[7][7] = "Mecanismo Relax; medidas aproximadas";
sheet.getRange("A1:H15").values = rows;
sheet.getRange("A1:H1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } };
sheet.getRange("A1:H15").format.wrapText = true; sheet.getRange("A1:A15").format.columnWidth = 14; sheet.getRange("B1:B15").format.columnWidth = 34; sheet.getRange("C1:C15").format.columnWidth = 28; sheet.getRange("D1:D15").format.columnWidth = 54; sheet.getRange("E1:F15").format.columnWidth = 38; sheet.getRange("G1:G15").format.columnWidth = 24; sheet.getRange("H1:H15").format.columnWidth = 42;
sheet.getRange("A1:H15").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" }; sheet.freezePanes.freezeRows(1);
const grouped = [
  ["Grupo", "Categoria construtiva", "Braços", "Modelo", "Medidas do assento", "Medidas do encosto", "Fonte / registro"],
  ["Cadeiras fixas", "Cadeiras em polipropileno injetado", "Braço/prancheta fixa", "Cadeira Universitária Fixa em Polipropileno com Prancheta", "aprox. 42 cm profundidade x 46 cm largura", "aprox. 28,0 cm altura x 46 cm largura", "UFRGS"],
  ["Cadeiras fixas", "Cadeiras em polipropileno injetado", "Não evidenciado", "Item 1 — Cadeira Fixa Empilhável", "aprox. 43 cm profundidade x 45 cm largura", "aprox. 30 cm altura x 45 cm largura", "Assistência Jurídica"],
  ["Cadeiras fixas", "Cadeiras estofadas", "Braço/prancheta fixa", "Cadeira Universitária Fixa Estofada com Prancheta", "aprox. 39 cm profundidade x 42 cm largura x 5 cm espessura", "aprox. 29 cm altura x 36 cm largura x 4 cm espessura", "UFRGS"],
  ["Cadeiras fixas", "Cadeiras estofadas", "Sem braços", "Modelo Fixa Estofada", "aprox. 42 cm profundidade x 43 cm largura", "aprox. 27 cm altura x 39 cm largura", "Prefeitura BH"],
  ["Cadeiras fixas", "Cadeiras estofadas", "Com braços", "Cadeira Fixa Universitária Executiva Com Braço Escamoteável", "aprox. 43,5 cm profundidade x 46 cm largura", "aprox. 37 cm altura x 42 cm largura", "Prefeitura BH universitária"],
  ["Cadeiras fixas", "Cadeiras estofadas", "Não evidenciado", "Item 6 — Cadeira Secretaria Fixa", "aprox. 39 cm profundidade x 42 cm largura", "aprox. 29 cm altura x 37 cm largura", "Patrocínio Paulista"],
  ["Cadeiras fixas", "Cadeiras estofadas", "Não evidenciado", "Item 10 — Cadeira Fixa", "aprox. 39 cm profundidade x 42 cm largura", "aprox. 29 cm altura x 37 cm largura", "Patrocínio Paulista"],
  ["Cadeiras giratórias", "Cadeiras estofadas", "Com braços", "Cadeira Ergonômica Com Braços", "aprox. 46 cm profundidade x 48 cm largura", "aprox. 47 cm altura x 44 cm largura", "CRECI"],
  ["Cadeiras giratórias", "Cadeiras estofadas", "Com braços", "Item 8 — Cadeira Executiva Lâmina Ergonômica", "aprox. 42 cm profundidade x 46 cm largura", "aprox. 37 cm altura x 40 cm largura", "Patrocínio Paulista"],
  ["Cadeiras giratórias", "Cadeiras com encosto em tela e assento estofado", "Com braços", "Cadeira Ergonômica Tela Com Braços", "aprox. 48 cm profundidade x 49 cm largura x 8 cm espessura", "aprox. 54 cm altura x 45 cm largura x 8 cm espessura", "São José dos Pinhais"],
  ["Cadeiras giratórias", "Cadeiras com encosto em tela e assento estofado", "Com braços", "Modelo Tela Ergonômica Relax com Braço", "aprox. 48 cm profundidade x 48 cm largura", "aprox. 56 cm altura x 48 cm largura", "Material Bélico Tela"],
  ["Cadeiras giratórias", "Cadeiras em poliuretano integral skin", "Não evidenciado", "Item 3 — Cadeira Injetada Industrial", "aprox. 41,5 cm profundidade x 43 cm largura x 4 cm espessura", "aprox. 25 cm altura x 40,5 cm largura x 4 cm espessura", "Material Bélico Injetado"],
  ["Bancos/cadeiras semi-sentados", "Bancos/cadeiras semi-sentados em PU", "Não evidenciado", "Item 2 — Banco Semi Sentado com Rodízios", "largura 35 cm x profundidade 28,5 cm", "altura 13 cm x largura 22 cm", "Material Bélico Injetado"],
  ["Cadeiras rebatíveis de auditório", "Cadeiras de auditório estofadas", "Com braços / prancheta escamoteável", "Cadeira de Auditório Rebatível com Braço e Prancheta Escamoteável", "aprox. 48 cm profundidade x 49 cm largura", "aprox. 48 cm altura x 46 cm largura", "Almirante Alexandrino"],
];
const groupedSheet = workbook.worksheets.add("Agrupado por tipo"); groupedSheet.showGridLines = false; groupedSheet.getRange("A1:G15").values = grouped; groupedSheet.getRange("A1:G1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF" } }; groupedSheet.getRange("A1:G15").format.wrapText = true; groupedSheet.getRange("A1:A15").format.columnWidth = 28; groupedSheet.getRange("B1:B15").format.columnWidth = 38; groupedSheet.getRange("C1:C15").format.columnWidth = 30; groupedSheet.getRange("D1:D15").format.columnWidth = 58; groupedSheet.getRange("E1:F15").format.columnWidth = 40; groupedSheet.getRange("G1:G15").format.columnWidth = 24; groupedSheet.getRange("A1:G15").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" }; groupedSheet.freezePanes.freezeRows(1);
const preview = await workbook.render({ sheetName: "Modelos", autoCrop: "all", scale: 1, format: "png" }); await fs.writeFile(`${out}/modelos-preview.png`, new Uint8Array(await preview.arrayBuffer()));
const groupedPreview = await workbook.render({ sheetName: "Agrupado por tipo", autoCrop: "all", scale: 1, format: "png" }); await fs.writeFile(`${out}/modelos-agrupados-preview.png`, new Uint8Array(await groupedPreview.arrayBuffer()));
const xlsx = await SpreadsheetFile.exportXlsx(workbook); await xlsx.save(`${out}/modelos-de-cadeiras-analisados.xlsx`);
