export const CLASSIFICATION_HASH = "#classificacoes";
export const LEGACY_CLASSIFICATION_HASH = "#bloco-6";

export function opensClassifications(hash: string): boolean {
  return [CLASSIFICATION_HASH, LEGACY_CLASSIFICATION_HASH].includes(hash);
}

