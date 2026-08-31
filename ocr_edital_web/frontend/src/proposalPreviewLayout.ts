import type {
  ProposalColumnKey,
  ProposalColumnWidths,
  ProposalItem,
} from "./types";

export interface ProposalColumnDefinition {
  key: ProposalColumnKey;
  label: string;
}

export interface ProposalRowFragment {
  id: string;
  item: ProposalItem;
  description: string;
  continuation: boolean;
}

export interface ProposalTablePage {
  rows: ProposalRowFragment[];
  remainingLines: number;
}

const CORE_COLUMNS: ProposalColumnDefinition[] = [
  { key: "item", label: "ITEM" },
  { key: "quantidade", label: "QTD" },
  { key: "unidade", label: "UND" },
  { key: "descricao", label: "DESCRIÇÃO" },
  { key: "marca", label: "MARCA" },
  { key: "valor_unitario", label: "VALOR UNITÁRIO" },
  { key: "valor_total", label: "VALOR TOTAL" },
];

const DEFAULT_WEIGHTS: Record<ProposalColumnKey, number> = {
  lote: 0,
  item: 650,
  quantidade: 650,
  unidade: 600,
  descricao: 4500,
  marca: 1200,
  valor_unitario: 1600,
  valor_total: 1900,
};

const DEFAULT_LOT_WEIGHTS: Record<ProposalColumnKey, number> = {
  lote: 750,
  item: 650,
  quantidade: 600,
  unidade: 600,
  descricao: 3850,
  marca: 1250,
  valor_unitario: 1550,
  valor_total: 1850,
};

export const PREVIEW_PAGE_LINE_CAPACITY = 72;
export const PREVIEW_TABLE_HEADER_LINES = 4;
export const MIN_COLUMN_WIDTH_PERCENT = 4;

export function proposalColumns(showLot: boolean): ProposalColumnDefinition[] {
  return showLot
    ? [{ key: "lote", label: "LOTE" }, ...CORE_COLUMNS]
    : CORE_COLUMNS;
}

export function normalizeProposalColumnWidths(
  widths: ProposalColumnWidths,
  showLot: boolean,
): ProposalColumnWidths {
  const columns = proposalColumns(showLot);
  const defaults = showLot ? DEFAULT_LOT_WEIGHTS : DEFAULT_WEIGHTS;
  const values = columns.map(({ key }) => {
    const candidate = widths[key];
    return typeof candidate === "number" && Number.isFinite(candidate) && candidate > 0
      ? candidate
      : defaults[key];
  });
  const total = values.reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(
    columns.map(({ key }, index) => [key, (values[index] / total) * 100]),
  ) as ProposalColumnWidths;
}

export function defaultProposalColumnWidths(showLot: boolean): ProposalColumnWidths {
  return normalizeProposalColumnWidths({}, showLot);
}

export function resizeAdjacentProposalColumns(
  widths: ProposalColumnWidths,
  showLot: boolean,
  leftKey: ProposalColumnKey,
  rightKey: ProposalColumnKey,
  deltaPercent: number,
): ProposalColumnWidths {
  const normalized = normalizeProposalColumnWidths(widths, showLot);
  const left = normalized[leftKey] || 0;
  const right = normalized[rightKey] || 0;
  const boundedDelta = Math.max(
    MIN_COLUMN_WIDTH_PERCENT - left,
    Math.min(deltaPercent, right - MIN_COLUMN_WIDTH_PERCENT),
  );
  return {
    ...normalized,
    [leftKey]: left + boundedDelta,
    [rightKey]: right - boundedDelta,
  };
}

export function estimatePreviewTextLines(text: string, charactersPerLine = 88): number {
  const paragraphs = String(text || "").split(/\r?\n/);
  return Math.max(1, paragraphs.reduce(
    (total, paragraph) => total + Math.max(1, Math.ceil(paragraph.length / charactersPerLine)),
    0,
  ));
}

function descriptionCharactersPerLine(widths: ProposalColumnWidths, showLot: boolean): number {
  const normalized = normalizeProposalColumnWidths(widths, showLot);
  return Math.max(12, Math.floor((normalized.descricao || 30) * 1.18));
}

function takeDescriptionChunk(text: string, maximumCharacters: number): [string, string] {
  if (text.length <= maximumCharacters) return [text, ""];
  const candidate = text.slice(0, maximumCharacters + 1);
  const wordBoundary = candidate.lastIndexOf(" ");
  const splitAt = wordBoundary >= Math.floor(maximumCharacters * 0.55)
    ? wordBoundary
    : maximumCharacters;
  return [text.slice(0, splitAt).trim(), text.slice(splitAt).trim()];
}

export function paginateProposalRows(
  items: ProposalItem[],
  widths: ProposalColumnWidths,
  showLot: boolean,
  firstPageLines: number,
  followingPageLines = PREVIEW_PAGE_LINE_CAPACITY - PREVIEW_TABLE_HEADER_LINES,
): ProposalTablePage[] {
  const charactersPerLine = descriptionCharactersPerLine(widths, showLot);
  const pages: ProposalTablePage[] = [];
  let availableLines = Math.max(2, firstPageLines);
  let rows: ProposalRowFragment[] = [];

  const finishPage = () => {
    pages.push({ rows, remainingLines: availableLines });
    rows = [];
    availableLines = Math.max(2, followingPageLines);
  };

  items.forEach((item, itemIndex) => {
    let remainingDescription = String(item.descricao || "").trim() || " ";
    let fragmentIndex = 0;
    while (remainingDescription) {
      if (availableLines < 3) finishPage();
      const availableTextLines = Math.max(1, availableLines - 1);
      const [description, rest] = takeDescriptionChunk(
        remainingDescription,
        charactersPerLine * availableTextLines,
      );
      const lineCost = Math.max(
        3,
        Math.min(
          availableLines,
          estimatePreviewTextLines(description, charactersPerLine) + 1,
        ),
      );
      rows.push({
        id: `${item.lote || ""}-${item.item}-${itemIndex}-${fragmentIndex}`,
        item,
        description,
        continuation: fragmentIndex > 0,
      });
      availableLines -= lineCost;
      remainingDescription = rest;
      fragmentIndex += 1;
      if (remainingDescription) finishPage();
    }
  });

  if (rows.length || !pages.length) finishPage();
  return pages;
}
