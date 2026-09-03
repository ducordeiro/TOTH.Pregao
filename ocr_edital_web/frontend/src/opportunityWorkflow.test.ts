import { afterEach, describe, expect, it, vi } from "vitest";
import { convertOpportunityToBusiness, createCatalogGeneratorJob, importBusiness } from "./api";
import { opportunityItemKey, selectedOpportunityItems } from "./opportunitySelection";
import type { OpportunityItem } from "./types";

const link = "https://pncp.gov.br/app/editais/01612623000188/2026/15";
const first: OpportunityItem = {
  numero: "1", lote: "1", descricao: "Cadeira", quantidade: "2", unidade: "UND",
  valor_unitario_estimado: null, valor_total_estimado: null,
  criterio_julgamento: "", situacao: "", tipo: "",
};
const second = { ...first, lote: "2" };

afterEach(() => vi.unstubAllGlobals());

describe("selected opportunity workflow requests", () => {
  it("sends only the selected lot/item keys to block 7", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "job" })));
    vi.stubGlobal("fetch", fetchMock);
    const selected = selectedOpportunityItems([first, second], new Set(["2/1"]));

    await createCatalogGeneratorJob(link, selected.map(opportunityItemKey));

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      pncp_link: link, selected_item_keys: ["2/1"],
    });
  });

  it("keeps empty selection explicit instead of silently requesting every item", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response("{}")));
    vi.stubGlobal("fetch", fetchMock);
    await createCatalogGeneratorJob(link, []);
    await createCatalogGeneratorJob(link);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).selected_item_keys).toEqual([]);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).not.toHaveProperty("selected_item_keys");
  });

  it("uploads a one-off Word template to block 7 without registering it globally", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "job" })));
    vi.stubGlobal("fetch", fetchMock);
    const template = new File(["docx"], "template-catalogo.docx", {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });

    await createCatalogGeneratorJob(link, ["2/1"], undefined, template);

    const request = fetchMock.mock.calls[0][1];
    const body = request.body as FormData;
    expect(request.method).toBe("POST");
    expect(request.headers).toBeUndefined();
    expect(body).toBeInstanceOf(FormData);
    expect(body.get("pncp_link")).toBe(link);
    expect(JSON.parse(String(body.get("selected_item_keys")))).toEqual(["2/1"]);
    expect((body.get("template_file") as File).name).toBe("template-catalogo.docx");
  });

  it("sends the same selected items to both block 4 import paths", async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response('{"negocio":{}}')));
    vi.stubGlobal("fetch", fetchMock);
    const selected = selectedOpportunityItems([first, second], new Set(["2/1"]));

    await convertOpportunityToBusiness("opportunity", selected);
    await importBusiness(link, "", selected);

    for (const call of fetchMock.mock.calls) {
      expect(JSON.parse(call[1].body).itens).toEqual([second]);
    }
  });
});
