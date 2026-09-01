import { describe, expect, it } from "vitest";
import {
  calculateItemTotal,
  isValidPncpUrl,
  normalizePncpUrl,
  normalizeMoney,
  parseMoneyToCents,
  sanitizeMoneyInput,
} from "./utils";

describe("money utilities", () => {
  it("normalizes Brazilian currency without floating point", () => {
    expect(parseMoneyToCents("R$ 1.250,90")).toBe(125090n);
    expect(normalizeMoney("1250,9")).toBe("R$ 1.250,90");
  });

  it("multiplies decimal quantities precisely", () => {
    expect(calculateItemTotal("2,5", "R$ 10,20")).toBe("R$ 25,50");
  });

  it("rejects negative values", () => {
    expect(parseMoneyToCents("-1,00")).toBeNull();
  });

  it("removes letters and currency symbols from monetary input", () => {
    expect(sanitizeMoneyInput("abcR$ 1.250,90xyz")).toBe("1.250,90");
    expect(sanitizeMoneyInput("10 reais")).toBe("10");
  });
});

describe("PNCP URL validation", () => {
  it("accepts the official domain", () => {
    expect(
      isValidPncpUrl("https://pncp.gov.br/app/editais/12345678000199/2026/10"),
    ).toBe(true);
  });

  it("normalizes common copied link variations", () => {
    expect(
      normalizePncpUrl("www.pncp.gov.br/app/editais/12345678000199/2026/10/?pagina=1"),
    ).toBe("https://pncp.gov.br/app/editais/12345678000199/2026/10");
    expect(
      normalizePncpUrl("/app/editais/12345678000199/2026/10#arquivos"),
    ).toBe("https://pncp.gov.br/app/editais/12345678000199/2026/10");
  });

  it("rejects lookalike domains", () => {
    expect(
      isValidPncpUrl("https://example.com/app/editais/12345678000199/2026/10"),
    ).toBe(false);
  });
});
