import type { OpportunityItem, OpportunityItemSelection, ProposalItem } from "./types";
import { itemKey, normalizePncpUrl } from "./utils";

export function opportunityItemKey(item: Pick<OpportunityItem, "lote" | "numero">): string {
  return itemKey({ lote: item.lote, item: item.numero });
}

export function selectedOpportunityItems(
  items: OpportunityItem[],
  keys: ReadonlySet<string>,
): OpportunityItem[] {
  return items.filter((item) => keys.has(opportunityItemKey(item)));
}

export function selectionForLink(
  selection: OpportunityItemSelection | null | undefined,
  link: string,
): OpportunityItemSelection | null {
  const normalizedLink = normalizePncpUrl(link);
  return selection && normalizedLink && normalizePncpUrl(selection.pncpLink) === normalizedLink
    ? selection
    : null;
}

export function proposalItemsFromSelection(items: OpportunityItem[]): ProposalItem[] {
  return items.map((item) => ({
    lote: item.lote,
    item: item.numero,
    descricao: item.descricao,
    quantidade: item.quantidade,
    unidade: item.unidade || "UND",
    marca: "",
    valor_unitario: "",
    valor_total: "",
  }));
}
