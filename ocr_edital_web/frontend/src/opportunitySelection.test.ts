import { describe, expect, it } from "vitest";
import type { OpportunityItem } from "./types";
import {
  opportunityItemKey,
  proposalItemsFromSelection,
  selectedOpportunityItems,
  selectionForLink,
} from "./opportunitySelection";

const link = "https://pncp.gov.br/app/editais/01612623000188/2026/15";
const item: OpportunityItem = {
  numero: "01", lote: "01", descricao: "Cadeira", quantidade: "2", unidade: "UN",
  valor_unitario_estimado: 150, valor_total_estimado: 300,
  criterio_julgamento: "", situacao: "", tipo: "Material",
};

describe("opportunity item selection", () => {
  it("keeps the same item number in different lots separate", () => {
    const items = [item, { ...item, lote: "02" }];
    expect(opportunityItemKey(item)).toBe("1/1");
    expect(selectedOpportunityItems(items, new Set(["2/1"]))).toEqual([items[1]]);
  });

  it("retains selected items outside the current search results", () => {
    const items = [item, { ...item, numero: "2", descricao: "Mesa" }];
    const keys = new Set(["1/1", "1/2"]);
    expect(selectedOpportunityItems(items.filter((entry) => entry.descricao === "Mesa"), keys))
      .toEqual([items[1]]);
    expect(selectedOpportunityItems(items, keys)).toEqual(items);
    expect(selectedOpportunityItems(items, new Set())).toEqual([]);
  });

  it("never applies a selection to a different opportunity", () => {
    const selection = { pncpLink: link, items: [item] };
    expect(selectionForLink(selection, `${link}/`)).toBe(selection);
    expect(selectionForLink(selection, link.replace("/15", "/16"))).toBeNull();
    expect(selectionForLink(selection, "")).toBeNull();
  });

  it("reuses the selected descriptions without turning estimates into offered prices", () => {
    expect(proposalItemsFromSelection([item])).toEqual([{
      lote: "01", item: "01", descricao: "Cadeira", quantidade: "2", unidade: "UN",
      marca: "", valor_unitario: "", valor_total: "",
    }]);
    expect(proposalItemsFromSelection([])).toEqual([]);
  });
});
