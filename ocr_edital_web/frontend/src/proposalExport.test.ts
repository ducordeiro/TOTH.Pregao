import { afterEach, describe, expect, it, vi } from "vitest";
import { generateProposal } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("proposal export format", () => {
  for (const format of [undefined, "pdf"] as const) {
    it(`sends ${format || "docx by default"} to the existing generation endpoint`, async () => {
      const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({
        download_url: "/download/test", filename: "test",
      }), { headers: { "Content-Type": "application/json" } }));
      vi.stubGlobal("fetch", fetch);
      await generateProposal([], "original-template", "source", "1", {
        prazo_entrega: "30 dias", prazo_pagamento: "30 dias", validade_proposta: "60 dias",
      }, ["box"], ["box", "table"], { box: "center" }, { descricao: 50 },
      { box: "Texto editado" }, null, null, format);
      const [url, request] = fetch.mock.calls[0];
      const body = JSON.parse(request.body);
      expect(url).toBe("/generate");
      expect(body.output_format).toBe(format || "docx");
      expect(body.template_ref).toBe("original-template");
      expect(body.mini_box_contents).toEqual({ box: "Texto editado" });
      expect(body.proposal_column_widths).toEqual({ descricao: 50 });
    });
  }
});
