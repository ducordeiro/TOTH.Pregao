interface PreferenceStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface ProposalPreferences {
  templateId: string;
  responsibleId: string;
}

const STORAGE_KEY = "toth.proposal.last-used.v1";
const EMPTY_PREFERENCES: ProposalPreferences = { templateId: "", responsibleId: "" };

const browserStorage = (): PreferenceStorage | null => {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
};

export function loadProposalPreferences(
  storage: PreferenceStorage | null = browserStorage(),
): ProposalPreferences {
  if (!storage) return { ...EMPTY_PREFERENCES };
  try {
    const parsed = JSON.parse(storage.getItem(STORAGE_KEY) || "{}") as Partial<ProposalPreferences>;
    return {
      templateId: typeof parsed.templateId === "string" ? parsed.templateId : "",
      responsibleId: typeof parsed.responsibleId === "string" ? parsed.responsibleId : "",
    };
  } catch {
    return { ...EMPTY_PREFERENCES };
  }
}

export function saveProposalPreferences(
  used: ProposalPreferences,
  storage: PreferenceStorage | null = browserStorage(),
): ProposalPreferences {
  const current = loadProposalPreferences(storage);
  const updated = {
    templateId: used.templateId || current.templateId,
    responsibleId: used.responsibleId || current.responsibleId,
  };
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // The current selection still works when browser storage is unavailable.
  }
  return updated;
}

export function automaticSelectionId<T extends { id: string }>(
  records: T[],
  currentId: string,
  lastUsedId: string,
  preferredId = "",
): string {
  return [preferredId, currentId, lastUsedId]
    .find((candidate) => records.some((record) => record.id === candidate))
    || records[0]?.id
    || "";
}
