import { describe, expect, it } from "vitest";
import { createKeywordHighlighter } from "./keywordHighlight";

function hits(text: string, terms: string[]) {
  const parts = createKeywordHighlighter(terms)(text);
  expect(parts.map((part) => part.text).join("")).toBe(text);
  return parts.filter((part) => part.highlighted).map((part) => part.text);
}

describe("keyword highlights", () => {
  it("matches repeated whole words and plural without highlighting rocadeira", () => {
    expect(hits("CADEIRA, cadeiras e roçadeira; cadeira.", ["cadeira"]))
      .toEqual(["CADEIRA", "cadeiras", "cadeira"]);
  });
  it("preserves accents, decomposed characters, punctuation and whitespace", () => {
    expect(hits("  GIRATÓRIA\n girato\u0301ria!", ["giratoria"]))
      .toEqual(["GIRATÓRIA", "girato\u0301ria"]);
  });
  it("only highlights matching phrase tokens with the same short gaps as search", () => {
    expect(hits("cadeira muito boa giratória; cadeira com base muito alta giratória", ["cadeira giratoria"]))
      .toEqual(["cadeira", "giratória"]);
  });
  it("supports alternatives and overlapping phrases without duplicating text", () => {
    expect(hits("cadeira giratória e mesa", ["cadeira;mesa", "cadeira giratoria"]))
      .toEqual(["cadeira", "giratória", "mesa"]);
  });
  it("keeps markup-looking input as original text and ignores empty terms", () => {
    expect(hits('<b>cadeira</b> <script>alert(1)</script>', ["cadeira"]))
      .toEqual(["cadeira"]);
    expect(hits("cadeira", ["", "  ", "[.*]"])).toEqual([]);
    expect(hits("", ["cadeira"])).toEqual([]);
  });
});
