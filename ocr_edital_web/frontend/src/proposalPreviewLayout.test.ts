import { describe, expect, it } from "vitest";
import {
  defaultProposalColumnWidths,
  normalizeProposalColumnWidths,
  paginateProposalRows,
  resizeAdjacentProposalColumns,
  proposalColumns,
  proposalTableWidthPt,
  defaultTableMetrics,
} from "./proposalPreviewLayout";
import type { ProposalItem, ProposalTableLayout } from "./types";

function proposalItem(description: string): ProposalItem {
  return {
    item: "1",
    quantidade: "1",
    unidade: "UND",
    descricao: description,
    marca: "Marca",
    valor_unitario: "R$ 40,00",
    valor_total: "R$ 40,00",
  };
}

describe("proposal preview layout", () => {
  it("uses the template printable width instead of the preview viewport width", () => {
    expect(proposalTableWidthPt(proposalColumns(false), false, defaultTableMetrics)).toBe(468);
    expect(proposalTableWidthPt(proposalColumns(false), false,
      { ...defaultTableMetrics, available_width_twips: 7200 })).toBe(360);
    expect(proposalTableWidthPt([{key: "descricao", label: "Descricao"}], false,
      defaultTableMetrics)).toBe(225);
  });
  it("uses edited headers, removed columns and multiple additional values", () => {
    const text = Array.from({ length: 300 }, (_, index) => `linha${index}`).join("\n");
    const layout: ProposalTableLayout = { columns: [
      { key: "descricao", label: "Produto" }, { key: "custom_a", label: "Garantia" },
      { key: "custom_b", label: "Modelo" },
    ], custom_values: { custom_a: [text], custom_b: ["XYZ"] } };
    expect(proposalColumns(false, null, layout)).toEqual(layout.columns);
    const widths = defaultProposalColumnWidths(false, null, layout);
    expect(widths.item).toBeUndefined();
    const pages = paginateProposalRows([proposalItem("Cadeira")], widths, false, 12, undefined, null, layout);
    expect(pages.length).toBeGreaterThan(1);
    expect(pages.flatMap((page) => page.rows).map((row) => row.cells?.custom_a).join(" ").split(/\s+/).filter(Boolean))
      .toEqual(text.split("\n"));
    expect(pages[0].rows[0].cells?.custom_b).toBe("XYZ");
    expect(pages.every((page) => page.remainingLines >= 0)).toBe(true);
  });
  it("places the additional column before the selected column, including lots", () => {
    const column = { title: "Garantia", position: 0, values: ["12 meses"] };
    expect(proposalColumns(true, column).map((entry) => entry.key).slice(0, 3))
      .toEqual(["extra_column", "lote", "item"]);
    expect(proposalColumns(false, { ...column, position: 7 }).at(-1)?.label).toBe("Garantia");
    const widths = defaultProposalColumnWidths(true, column);
    const resized = resizeAdjacentProposalColumns(widths, true, "extra_column", "lote", 1, column);
    expect(resized.extra_column).toBeCloseTo(widths.extra_column! + 1);
    expect(Object.values(resized).reduce<number>((sum, value) => sum + (value || 0), 0)).toBeCloseTo(100);
  });

  it("preserves additional values on their rows and across continuation pages", () => {
    const text = Array.from({ length: 300 }, (_, index) => `valor${index}`).join(" ");
    const column = { title: "Observações", position: 3, values: [text, "", "Último valor"] };
    const items = [proposalItem("Primeiro"), proposalItem("Segundo"), proposalItem("Terceiro")];
    const rows = paginateProposalRows(items, defaultProposalColumnWidths(false, column), false, 18, undefined, column)
      .flatMap((page) => page.rows);
    expect(rows.filter((row) => row.item === items[0]).map((row) => row.extraValue).join(" ")).toBe(text);
    expect(rows.find((row) => row.item === items[1])?.extraValue).toBe("");
    expect(rows.find((row) => row.item === items[2])?.extraValue).toBe("Último valor");
  });

  it("paginates explicit line breaks in the additional column", () => {
    const column = { title: "Detalhes", position: 7, values: [Array(100).fill("Linha").join("\n")] };
    const pages = paginateProposalRows([proposalItem("Cadeira")], defaultProposalColumnWidths(false, column), false, 18, undefined, column);
    expect(pages.length).toBeGreaterThan(1);
    expect(pages.flatMap((page) => page.rows).flatMap((row) => row.extraValue!.split(/\s+/)).filter(Boolean)).toHaveLength(100);
  });
  it("keeps normalized column widths at one hundred percent", () => {
    const widths = normalizeProposalColumnWidths({}, false);
    const total = Object.values(widths).reduce<number>((sum, value) => sum + (value || 0), 0);

    expect(total).toBeCloseTo(100, 8);
    expect(widths.descricao).toBeGreaterThan(widths.item || 0);
  });

  it("resizes only adjacent columns and respects the minimum width", () => {
    const original = defaultProposalColumnWidths(false);
    const resized = resizeAdjacentProposalColumns(
      original,
      false,
      "descricao",
      "marca",
      50,
    );

    expect(resized.marca).toBe(4);
    expect(resized.descricao).toBeGreaterThan(original.descricao || 0);
    expect(resized.item).toBeCloseTo(original.item || 0, 8);
  });

  it("splits an oversized description across preview pages without losing text", () => {
    const description = Array.from({ length: 260 }, (_, index) => `palavra${index}`).join(" ");
    const pages = paginateProposalRows(
      [proposalItem(description)],
      defaultProposalColumnWidths(false),
      false,
      18,
    );
    const rebuilt = pages
      .flatMap((page) => page.rows)
      .map((row) => row.description)
      .join(" ");

    expect(pages.length).toBeGreaterThan(1);
    expect(rebuilt).toBe(description);
    expect(pages.slice(1).every((page) => page.rows[0]?.continuation)).toBe(true);
  });
});
