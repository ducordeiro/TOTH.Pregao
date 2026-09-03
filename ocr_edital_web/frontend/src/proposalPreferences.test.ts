import { describe, expect, it } from "vitest";
import {
  automaticSelectionId,
  loadProposalPreferences,
  saveProposalPreferences,
} from "./proposalPreferences";

const memoryStorage = () => {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) || null,
    setItem: (key: string, value: string) => values.set(key, value),
  };
};

describe("block 2 proposal preferences", () => {
  it("stores the last managed template and responsible actually used", () => {
    const storage = memoryStorage();

    saveProposalPreferences(
      { templateId: "modelo.docx", responsibleId: "responsavel-2" },
      storage,
    );

    expect(loadProposalPreferences(storage)).toEqual({
      templateId: "modelo.docx",
      responsibleId: "responsavel-2",
    });
  });

  it("keeps the last managed template when a one-off file is used", () => {
    const storage = memoryStorage();
    saveProposalPreferences(
      { templateId: "modelo.docx", responsibleId: "responsavel-1" },
      storage,
    );

    const updated = saveProposalPreferences(
      { templateId: "", responsibleId: "responsavel-2" },
      storage,
    );

    expect(updated).toEqual({
      templateId: "modelo.docx",
      responsibleId: "responsavel-2",
    });
  });

  it("falls back to the first available record when the last one was removed", () => {
    const records = [{ id: "primeiro" }, { id: "segundo" }];

    expect(automaticSelectionId(records, "", "removido")).toBe("primeiro");
    expect(automaticSelectionId(records, "segundo", "primeiro")).toBe("segundo");
  });
});
