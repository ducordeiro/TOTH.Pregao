import type {
  ProposalColumnKey,
  ProposalColumnWidths,
  ProposalItem,
  ProposalExtraColumn,
  ProposalTableLayout,
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
  extraValue?: string;
  cells?: Record<string, string>;
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
  extra_column: 1500,
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
  extra_column: 1500,
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

export function proposalColumns(showLot: boolean, extraColumn?: ProposalExtraColumn | null, layout?: ProposalTableLayout | null): ProposalColumnDefinition[] {
  if (layout) return layout.columns;
  const columns = showLot
    ? [{ key: "lote", label: "LOTE" }, ...CORE_COLUMNS]
    : [...CORE_COLUMNS];
  if (extraColumn) columns.splice(extraColumn.position, 0, { key: "extra_column", label: extraColumn.title });
  return columns as ProposalColumnDefinition[];
}

export function normalizeProposalColumnWidths(
  widths: ProposalColumnWidths,
  showLot: boolean,
  extraColumn?: ProposalExtraColumn | null,
  layout?: ProposalTableLayout | null,
): ProposalColumnWidths {
  const columns = proposalColumns(showLot, extraColumn, layout);
  const defaults = showLot ? DEFAULT_LOT_WEIGHTS : DEFAULT_WEIGHTS;
  const values = columns.map(({ key }) => {
    const candidate = widths[key];
    return typeof candidate === "number" && Number.isFinite(candidate) && candidate > 0
      ? candidate
      : defaults[key] || 1500;
  });
  const total = values.reduce((sum, value) => sum + value, 0);
  return Object.fromEntries(
    columns.map(({ key }, index) => [key, (values[index] / total) * 100]),
  ) as ProposalColumnWidths;
}

export function defaultProposalColumnWidths(showLot: boolean, extraColumn?: ProposalExtraColumn | null, layout?: ProposalTableLayout | null): ProposalColumnWidths {
  return normalizeProposalColumnWidths({}, showLot, extraColumn, layout);
}

export function resizeAdjacentProposalColumns(
  widths: ProposalColumnWidths,
  showLot: boolean,
  leftKey: ProposalColumnKey,
  rightKey: ProposalColumnKey,
  deltaPercent: number,
  extraColumn?: ProposalExtraColumn | null,
  layout?: ProposalTableLayout | null,
): ProposalColumnWidths {
  const normalized = normalizeProposalColumnWidths(widths, showLot, extraColumn, layout);
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

function descriptionCharactersPerLine(widths: ProposalColumnWidths, showLot: boolean, extraColumn?: ProposalExtraColumn | null): number {
  const normalized = normalizeProposalColumnWidths(widths, showLot, extraColumn);
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
  extraColumn?: ProposalExtraColumn | null,
  layout?: ProposalTableLayout | null,
): ProposalTablePage[] {
  if (layout) return paginateEditedTable(items, widths, showLot, firstPageLines, followingPageLines, layout);
  const charactersPerLine = descriptionCharactersPerLine(widths, showLot, extraColumn);
  const extraCharactersPerLine = Math.max(4, Math.floor(
    (normalizeProposalColumnWidths(widths, showLot, extraColumn).extra_column || 12) * 1.18,
  ));
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
    let remainingExtra = extraColumn?.values[itemIndex] || "";
    let fragmentIndex = 0;
    while (remainingDescription || remainingExtra) {
      if (availableLines < 3) finishPage();
      const availableTextLines = Math.max(1, availableLines - 1);
      const [description, rest] = takeDescriptionChunk(
        remainingDescription,
        charactersPerLine * availableTextLines,
      );
      let low = 0;
      let high = Math.min(remainingExtra.length, extraCharactersPerLine * availableTextLines);
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        if (estimatePreviewTextLines(remainingExtra.slice(0, middle), extraCharactersPerLine) <= availableTextLines) low = middle;
        else high = middle - 1;
      }
      const [extraValue, extraRest] = takeDescriptionChunk(remainingExtra, Math.max(1, low));
      const lineCost = Math.max(
        3,
        Math.min(
          availableLines,
          Math.max(estimatePreviewTextLines(description, charactersPerLine),
            estimatePreviewTextLines(extraValue, extraCharactersPerLine)) + 1,
        ),
      );
      rows.push({
        id: `${item.lote || ""}-${item.item}-${itemIndex}-${fragmentIndex}`,
        item,
        description,
        continuation: fragmentIndex > 0,
        extraValue,
      });
      availableLines -= lineCost;
      remainingDescription = rest;
      remainingExtra = extraRest;
      fragmentIndex += 1;
      if (remainingDescription || remainingExtra) finishPage();
    }
  });

  if (rows.length || !pages.length) finishPage();
  return pages;
}

export function proposalCellValue(item: ProposalItem, index: number, key: ProposalColumnKey, layout?: ProposalTableLayout | null): string {
  if (key.startsWith("custom_")) return layout?.custom_values[key]?.[index] || "";
  if (key === "extra_column") return "";
  return String(item[key as keyof ProposalItem] ?? (key === "unidade" ? "UND" : ""));
}

function paginateEditedTable(items: ProposalItem[], widths: ProposalColumnWidths, showLot: boolean,
  firstLines: number, nextLines: number, layout: ProposalTableLayout): ProposalTablePage[] {
  const normalized = normalizeProposalColumnWidths(widths, showLot, null, layout);
  const pages: ProposalTablePage[] = [];
  let rows: ProposalRowFragment[] = [];
  let available = Math.max(3, firstLines);
  const finish = () => { pages.push({ rows, remainingLines: available }); rows = []; available = Math.max(3, nextLines); };
  items.forEach((item, index) => {
    let values = layout.columns.map(({ key }) => proposalCellValue(item, index, key, layout));
    let fragment = 0;
    do {
      if (available < 3) finish();
      const cells: Record<string, string> = {};
      let cost = 3;
      values = values.map((text, columnIndex) => {
        const key = layout.columns[columnIndex].key;
        const perLine = Math.max(4, Math.floor((normalized[key] || 12) * 1.18));
        let low = 0, high = Math.min(text.length, perLine * (available - 1));
        while (low < high) {
          const mid = Math.ceil((low + high) / 2);
          if (estimatePreviewTextLines(text.slice(0, mid), perLine) <= available - 1) low = mid;
          else high = mid - 1;
        }
        const [part, rest] = takeDescriptionChunk(text, Math.max(1, low));
        cells[key] = part;
        cost = Math.max(cost, Math.min(available, estimatePreviewTextLines(part, perLine) + 1));
        return rest;
      });
      rows.push({ id: `edited-${index}-${fragment}`, item, description: cells.descricao || "", continuation: fragment > 0, cells });
      available -= cost;
      fragment++;
      if (values.some(Boolean)) finish();
    } while (values.some(Boolean));
  });
  if (rows.length || !pages.length) finish();
  return pages;
}
