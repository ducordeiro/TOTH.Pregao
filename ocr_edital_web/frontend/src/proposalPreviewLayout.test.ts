import { describe, expect, it } from "vitest";
import {
  defaultProposalColumnWidths,
  normalizeProposalColumnWidths,
  paginateProposalRows,
  resizeAdjacentProposalColumns,
} from "./proposalPreviewLayout";
import type { ProposalItem } from "./types";

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
  it("keeps normalized column widths at one hundred percent", () => {
    const widths = normalizeProposalColumnWidths({}, false);
    const total = Object.values(widths).reduce((sum, value) => sum + (value || 0), 0);

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
