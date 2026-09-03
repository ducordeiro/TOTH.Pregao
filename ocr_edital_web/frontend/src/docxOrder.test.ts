import { describe, expect, it } from "vitest";
import {
  applyMiniBoxOrder,
  createDocumentBlockOrder,
  createReplicaDocumentBlocks,
  insertDocumentBlockBefore,
  miniBoxOrder,
  miniBoxOrderFromDocumentOrder,
  moveDocumentBlock,
  moveMiniBox,
  reorderDocumentBlocks,
  reorderMiniBoxes,
  withoutTemplateHeader,
} from "./docxOrder";
import type { DocumentNode } from "./types";

const nodes: DocumentNode[] = [
  { id: "fixed-a", type: "FIXED_TEXT", content: "Antes" },
  { id: "box-a", type: "MINI_BOX", content: "A", order: 0, text_align: "left" },
  { id: "fixed-b", type: "FIXED_TEXT", content: "Entre" },
  { id: "box-b", type: "MINI_BOX", content: "B", order: 1, text_align: "left" },
  { id: "box-c", type: "MINI_BOX", content: "C", order: 2, text_align: "center" },
];

describe("DOCX mini-box ordering", () => {
  it("updates only MINI_BOX order and leaves FIXED_TEXT in place", () => {
    const reordered = reorderMiniBoxes(nodes, "box-c", "box-a");

    expect(miniBoxOrder(reordered)).toEqual(["box-c", "box-a", "box-b"]);
    expect(reordered[0]).toBe(nodes[0]);
    expect(reordered[2]).toBe(nodes[2]);
  });

  it("supports deterministic one-position moves", () => {
    expect(miniBoxOrder(moveMiniBox(nodes, "box-b", -1))).toEqual([
      "box-b",
      "box-a",
      "box-c",
    ]);
    expect(moveMiniBox(nodes, "box-a", -1)).toBe(nodes);
  });

  it("ignores unknown and no-op drag targets", () => {
    expect(reorderMiniBoxes(nodes, "missing", "box-a")).toBe(nodes);
    expect(reorderMiniBoxes(nodes, "box-a", "box-a")).toBe(nodes);
  });

  it("keeps the generated table in the complete visual order", () => {
    const tableId = "generated-table";
    const initial = createDocumentBlockOrder(nodes, tableId);
    const reordered = reorderDocumentBlocks(initial, tableId, "box-b");

    expect(reordered).toEqual(["box-a", tableId, "box-b", "box-c"]);
    expect(miniBoxOrderFromDocumentOrder(reordered, tableId)).toEqual([
      "box-a",
      "box-b",
      "box-c",
    ]);
    expect(miniBoxOrder(applyMiniBoxOrder(nodes, ["box-c", "box-a", "box-b"]))).toEqual([
      "box-c",
      "box-a",
      "box-b",
    ]);
  });

  it("supports accessible moves and insertion from the table dock", () => {
    const initial = ["box-a", "box-b", "box-c", "generated-table"];

    expect(moveDocumentBlock(initial, "box-c", -1)).toEqual([
      "box-a",
      "box-c",
      "box-b",
      "generated-table",
    ]);
    expect(insertDocumentBlockBefore(initial, "generated-table", "box-b")).toEqual([
      "box-a",
      "generated-table",
      "box-b",
      "box-c",
    ]);
  });

  it("builds the replica from the transient visual order while preserving fixed text", () => {
    const table = {
      id: "generated-table",
      type: "GENERATED_TABLE" as const,
      content: "Tabela gerada",
    };
    const replica = createReplicaDocumentBlocks(
      nodes,
      ["box-c", table.id, "box-a", "box-b"],
      table,
    );

    expect(replica.map((block) => block.id)).toEqual([
      "fixed-a",
      "box-c",
      "fixed-b",
      table.id,
      "box-a",
      "box-b",
    ]);
    expect(replica.filter((block) => block.type === "FIXED_TEXT").map((block) => block.content))
      .toEqual(["Antes", "Entre"]);
  });

  it("removes an excluded mini-box from the replica without removing fixed text", () => {
    const table = {
      id: "generated-table",
      type: "GENERATED_TABLE" as const,
      content: "Tabela gerada",
    };
    const replica = createReplicaDocumentBlocks(
      nodes,
      ["box-c", "box-a", table.id],
      table,
    );

    expect(replica.map((block) => block.id)).toEqual([
      "fixed-a",
      "box-c",
      "fixed-b",
      "box-a",
      table.id,
    ]);
    expect(replica.some((block) => block.id === "box-b")).toBe(false);
  });

  it("falls back to the original replica order when the visual order is invalid", () => {
    const table = {
      id: "generated-table",
      type: "GENERATED_TABLE" as const,
      content: "Tabela gerada",
    };
    const replica = createReplicaDocumentBlocks(nodes, ["box-a"], table);

    expect(replica.filter((block) => block.type !== "FIXED_TEXT").map((block) => block.id))
      .toEqual(["box-a", "box-b", "box-c", table.id]);
  });

  it("omits template header content only from the live preview", () => {
    const table = {
      id: "generated-table",
      type: "GENERATED_TABLE" as const,
      content: "Tabela gerada",
    };
    const scopedNodes: DocumentNode[] = [
      { id: "body", type: "FIXED_TEXT", content: "Corpo", source_part: "word/document.xml" },
      { id: "body-box", type: "MINI_BOX", content: "Item", order: 0, text_align: "left", source_part: "word/document.xml" },
      { id: "header", type: "FIXED_TEXT", content: "Cabeçalho", source_part: "word/header1.xml" },
      { id: "header-box", type: "MINI_BOX", content: "Marca", order: 1, text_align: "center", source_part: "word/header1.xml" },
    ];

    const replica = createReplicaDocumentBlocks(
      scopedNodes,
      ["body-box", "header-box", table.id],
      table,
    );

    expect(withoutTemplateHeader(replica).map((block) => block.id)).toEqual([
      "body",
      "body-box",
      table.id,
    ]);
    expect(replica.map((block) => block.id)).toContain("header-box");
  });
});
