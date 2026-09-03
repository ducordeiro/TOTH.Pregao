import { describe, expect, it } from "vitest";
import { CLASSIFICATION_HASH, LEGACY_CLASSIFICATION_HASH, opensClassifications } from "./classificationNavigation";

describe("navegação das classificações", () => {
  it("abre pela âncora do Bloco 5", () => {
    expect(opensClassifications(CLASSIFICATION_HASH)).toBe(true);
  });

  it("mantém compatibilidade com o acesso antigo do Bloco 6", () => {
    expect(opensClassifications(LEGACY_CLASSIFICATION_HASH)).toBe(true);
  });

  it("não interfere nas demais áreas", () => {
    expect(opensClassifications("#negocio-10")).toBe(false);
    expect(opensClassifications("")).toBe(false);
  });
});
