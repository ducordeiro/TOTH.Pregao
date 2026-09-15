import { useCallback, useMemo, useLayoutEffect, useRef, useState } from "react";
import { TemplatePagePart } from "./TemplatePagePart";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import type { ReactNode } from "react";
import { FileText, RotateCcw } from "lucide-react";
import { createReplicaDocumentBlocks, splitReplicaPageParts } from "../docxOrder";
import type { ReplicaDocumentBlock } from "../docxOrder";
import {
  PREVIEW_PAGE_LINE_CAPACITY,
  PREVIEW_TABLE_HEADER_LINES,
  defaultProposalColumnWidths,
  defaultTableMetrics,
  proposalTableWidthPt,
  estimatePreviewTextLines,
  normalizeProposalColumnWidths,
  paginateProposalRows,
  proposalColumns,
  resizeAdjacentProposalColumns,
} from "../proposalPreviewLayout";
import type {
  ProposalColumnDefinition,
  ProposalRowFragment,
} from "../proposalPreviewLayout";
import type {
  CommercialTerms,
  DocumentNode,
  GeneratedTableBlock,
  MiniBoxTextAlign,
  ProposalColumnKey,
  ProposalColumnWidths,
  ProposalItem,
  ProposalExtraColumn,
  ProposalTableLayout,
  Responsible,
  ProposalTableMetrics,
  TemplatePagePartsPreview,
} from "../types";
import { formatCents, parseMoneyToCents } from "../utils";

interface ProposalLivePreviewProps {
  pagePartsPreview?: TemplatePagePartsPreview;
  tableMetrics?: ProposalTableMetrics;
  nodes: DocumentNode[];
  blockOrder: string[];
  generatedTable: GeneratedTableBlock;
  items: ProposalItem[];
  commercialTerms: CommercialTerms;
  responsible?: Responsible;
  miniBoxAlignments: Record<string, MiniBoxTextAlign>;
  columnWidths: ProposalColumnWidths;
  onColumnWidthsChange?: (widths: ProposalColumnWidths) => void;
  extraColumn?: ProposalExtraColumn | null;
  tableLayout?: ProposalTableLayout | null;
}

function ReplicaPage({ preview, children }: { preview?: TemplatePagePartsPreview; children: ReactNode }) {
  const page = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(0);
  useLayoutEffect(() => {
    if (!preview || !page.current) return;
    const element = page.current;
    const update = () => setWidth(element.getBoundingClientRect().width);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [preview]);
  const scale = preview && width ? width / preview.page_width_pt : 0;
  return <article ref={page} className="proposal-replica-page" style={preview && scale ? {
    paddingLeft: preview.left_margin_pt * scale,
    paddingRight: preview.right_margin_pt * scale,
    paddingTop: preview.header_distance_pt * scale,
    paddingBottom: preview.footer_distance_pt * scale,
    minHeight: preview.page_height_pt * scale,
  } : undefined}>{children}</article>;
}

function proposalTotal(items: ProposalItem[]): string {
  const cents = items.reduce((total, item) => {
    const itemCents = parseMoneyToCents(item.valor_total || "");
    return total + (itemCents || 0n);
  }, 0n);
  return formatCents(cents);
}

function columnValue(row: ProposalRowFragment, key: ProposalColumnKey): string {
  if (row.cells) return row.cells[key] || "";
  if (key === "extra_column") return row.extraValue || "";
  if (key === "descricao") return row.description;
  if (row.continuation) return "";
  if (key === "unidade") return String(row.item.unidade || "UND");
  return String(row.item[key as keyof ProposalItem] || "");
}

export function ColumnResizeHandle({
  left,
  right,
  widths,
  showLot,
  onChange,
  extraColumn,
  tableLayout,
}: {
  left: ProposalColumnKey;
  right: ProposalColumnKey;
  widths: ProposalColumnWidths;
  showLot: boolean;
  onChange: (widths: ProposalColumnWidths) => void;
  extraColumn?: ProposalExtraColumn | null;
  tableLayout?: ProposalTableLayout | null;
}) {
  const resizeBy = (deltaPercent: number) => {
    onChange(resizeAdjacentProposalColumns(widths, showLot, left, right, deltaPercent, extraColumn, tableLayout));
  };
  const handlePointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
    event.stopPropagation();
    const startX = event.clientX;
    const tableWidth = event.currentTarget.closest("table")?.getBoundingClientRect().width || 1;
    const initialWidths = widths;
    const handleMove = (moveEvent: PointerEvent) => {
      const deltaPercent = ((moveEvent.clientX - startX) / tableWidth) * 100;
      onChange(
        resizeAdjacentProposalColumns(initialWidths, showLot, left, right, deltaPercent, extraColumn, tableLayout),
      );
    };
    const handleEnd = () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerup", handleEnd);
      window.removeEventListener("pointercancel", handleEnd);
    };
    window.addEventListener("pointermove", handleMove);
    window.addEventListener("pointerup", handleEnd, { once: true });
    window.addEventListener("pointercancel", handleEnd, { once: true });
  };
  const handleKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    resizeBy(event.key === "ArrowLeft" ? -1 : 1);
  };
  return (
    <button
      type="button"
      className="proposal-column-resizer"
      aria-label={`Redimensionar colunas ${left} e ${right}`}
      title="Arraste para ajustar as colunas"
      onPointerDown={handlePointerDown}
      onKeyDown={handleKeyDown}
    />
  );
}

function ReplicaTable({
  rows,
  columns,
  widths,
  showLot,
  onWidthsChange,
  extraColumn,
  tableLayout,
  metrics,
}: {
  metrics: ProposalTableMetrics;
  rows: ProposalRowFragment[];
  columns: ProposalColumnDefinition[];
  widths: ProposalColumnWidths;
  showLot: boolean;
  onWidthsChange?: (widths: ProposalColumnWidths) => void;
  extraColumn?: ProposalExtraColumn | null;
  tableLayout?: ProposalTableLayout | null;
}) {
  const container = useRef<HTMLDivElement>(null);
  const physicalWidthPt = proposalTableWidthPt(columns, showLot, metrics);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const element = container.current;
    if (!element) return;
    const update = () => {
      const width = element.getBoundingClientRect().width;
      if (width > 0) setScale(width / (physicalWidthPt * 96 / 72));
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [physicalWidthPt]);
  const padding = (key: string) => {
    const horizontal = ["lote", "item", "quantidade", "unidade"].includes(key)
      ? metrics.narrow_padding_twips : metrics.horizontal_padding_twips;
    return `${metrics.vertical_padding_twips / 20}pt ${horizontal / 20}pt`;
  };
  return (
    <div className="proposal-replica-table-wrap" ref={container}>
      <table className="proposal-replica-table" style={{ width: `${physicalWidthPt}pt`, zoom: scale, fontSize: `${metrics.body_font_pt}pt` }}>
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={{ width: `${widths[column.key] || 0}%` }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th key={column.key} style={{ padding: padding(column.key), fontSize: `${metrics.header_font_pt}pt` }}>
                {column.label}
                {onWidthsChange && index < columns.length - 1 && (
                  <ColumnResizeHandle
                    left={column.key}
                    right={columns[index + 1].key}
                    widths={widths}
                    showLot={showLot}
                    onChange={onWidthsChange}
                    extraColumn={extraColumn}
                    tableLayout={tableLayout}
                  />
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className={row.continuation ? "is-continuation" : undefined}>
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={column.key === "descricao" ? "proposal-replica-description" : undefined}
                  style={{ padding: padding(column.key), whiteSpace: "pre-wrap" }}
                >
                  {columnValue(row, column.key)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function documentBlocksLineCost(blocks: ReplicaDocumentBlock[]): number {
  return blocks.reduce((total, block) => (
    total + estimatePreviewTextLines(block.content, 86) + 1
  ), 0);
}

function trailingLineCost(blocks: ReplicaDocumentBlock[], responsible?: Responsible): number {
  const responsibleLines = responsible
    ? 3 + [responsible.empresa, responsible.nome_completo, responsible.rg, responsible.cpf]
      .filter(Boolean).length
    : 0;
  return documentBlocksLineCost(blocks) + 9 + responsibleLines;
}

function DocumentBlocks({
  blocks,
  alignments,
}: {
  blocks: ReplicaDocumentBlock[];
  alignments: Record<string, MiniBoxTextAlign>;
}) {
  return blocks.map((block, index) => {
    if (block.type === "GENERATED_TABLE") return null;
    const content = block.content.trim();
    if (!content) return null;
    return block.type === "MINI_BOX" ? (
      <section
        className="proposal-replica-mini-box"
        key={`${block.id}-${index}`}
        style={{ textAlign: alignments[block.id] || block.text_align }}
      >
        {content}
      </section>
    ) : (
      <p className="proposal-replica-fixed-text" key={`${block.id}-${index}`}>
        {content}
      </p>
    );
  });
}

function ProposalTrailingContent({
  items,
  commercialTerms,
  responsible,
}: {
  items: ProposalItem[];
  commercialTerms: CommercialTerms;
  responsible?: Responsible;
}) {
  return (
    <>
      <div className="proposal-replica-terms">
        <p><strong>VALOR TOTAL DA PROPOSTA:</strong> {proposalTotal(items)}</p>
        <p><strong>Prazo de Entrega:</strong> {commercialTerms.prazo_entrega}</p>
        <p><strong>Prazo de pagamento:</strong> {commercialTerms.prazo_pagamento}</p>
        <p><strong>Validade da Proposta:</strong> {commercialTerms.validade_proposta}</p>
      </div>
      {responsible && (
        <div className="proposal-replica-responsible">
          {responsible.empresa && <p>{responsible.empresa}</p>}
          <p>{responsible.nome_completo}</p>
          {responsible.rg && <p>RG {responsible.rg}</p>}
          {responsible.cpf && <p>CPF {responsible.cpf}</p>}
        </div>
      )}
    </>
  );
}

export function ProposalLivePreview({
  nodes,
  blockOrder,
  generatedTable,
  items,
  commercialTerms,
  responsible,
  miniBoxAlignments,
  columnWidths,
  onColumnWidthsChange,
  extraColumn,
  tableLayout,
  tableMetrics = defaultTableMetrics,
  pagePartsPreview,
}: ProposalLivePreviewProps) {
  const [partHeights, setPartHeights] = useState({ key: "", header: 0, footer: 0 });
  const reportPartHeight = useCallback((kind: "header" | "footer", height: number) => {
    const key = pagePartsPreview?.docx_base64 || "";
    setPartHeights((current) => {
      const next = current.key === key ? current : { key, header: 0, footer: 0 };
      return height <= next[kind] + 0.5 ? next : { ...next, [kind]: height };
    });
  }, [pagePartsPreview?.docx_base64]);
  const showLot = items.some((item) => Boolean(String(item.lote || "").trim()));
  const columns = proposalColumns(showLot, extraColumn, tableLayout);
  const normalizedWidths = normalizeProposalColumnWidths(columnWidths, showLot, extraColumn, tableLayout);
  const { body: blocks, header, footer } = splitReplicaPageParts(
    createReplicaDocumentBlocks(nodes, blockOrder, generatedTable),
  );
  const tableIndex = blocks.findIndex((block) => block.type === "GENERATED_TABLE");
  const beforeBlocks = tableIndex >= 0 ? blocks.slice(0, tableIndex) : blocks;
  const afterBlocks = tableIndex >= 0 ? blocks.slice(tableIndex + 1) : [];
  const pageLineCapacity = Math.max(
    6,
    PREVIEW_PAGE_LINE_CAPACITY - (pagePartsPreview && partHeights.key === pagePartsPreview.docx_base64
      ? Math.ceil((partHeights.header + partHeights.footer) / 10)
      : documentBlocksLineCost(header) + documentBlocksLineCost(footer)),
  );
  const firstPageLines = Math.max(
    2,
    pageLineCapacity
      - PREVIEW_TABLE_HEADER_LINES
      - documentBlocksLineCost(beforeBlocks),
  );
  const tablePages = useMemo(
    () => paginateProposalRows(items, normalizedWidths, showLot, firstPageLines, pageLineCapacity - PREVIEW_TABLE_HEADER_LINES, extraColumn, tableLayout),
    [firstPageLines, pageLineCapacity, items, normalizedWidths, showLot, extraColumn, tableLayout],
  );
  const lastTablePage = tablePages[tablePages.length - 1];
  const finalContentLines = trailingLineCost(afterBlocks, responsible);
  const trailingFitsLastTablePage = lastTablePage.remainingLines >= finalContentLines;
  const pageCount = tablePages.length + (trailingFitsLastTablePage ? 0 : 1);
  const defaultWidths = defaultProposalColumnWidths(showLot, extraColumn, tableLayout);
  const hasCustomWidths = columns.some(
    ({ key }) => Math.abs((normalizedWidths[key] || 0) - (defaultWidths[key] || 0)) > 0.01,
  );

  return (
    <section className="proposal-live-preview" aria-label="Pré-visualização simultânea da proposta">
      <div className="proposal-replica-toolbar">
        <div>
          <FileText size={14} aria-hidden="true" />
          <span>Prévia da proposta</span>
        </div>
        {onColumnWidthsChange && hasCustomWidths && (
          <button
            type="button"
            className="proposal-replica-reset-columns"
            onClick={() => onColumnWidthsChange(defaultWidths)}
            aria-label="Restaurar largura das colunas"
            title="Restaurar colunas"
          >
            <RotateCcw size={14} />
          </button>
        )}
      </div>
      <div className="proposal-replica-viewport">
        {tablePages.map((page, pageIndex) => {
          const isLastTablePage = pageIndex === tablePages.length - 1;
          return (
            <ReplicaPage preview={pagePartsPreview} key={`page-${pageIndex + 1}`}>
              {(pagePartsPreview || header.length > 0) && (
                <div className="proposal-replica-template-header">
                  {pagePartsPreview ? <TemplatePagePart preview={pagePartsPreview} kind="header" pageIndex={pageIndex} onHeight={reportPartHeight} />
                    : <DocumentBlocks blocks={header} alignments={miniBoxAlignments} />}
                </div>
              )}
              <div className="proposal-replica-body">
              {pageIndex === 0 && (
                <DocumentBlocks blocks={beforeBlocks} alignments={miniBoxAlignments} />
              )}
              <ReplicaTable
                metrics={tableMetrics}
                rows={page.rows}
                columns={columns}
                widths={normalizedWidths}
                showLot={showLot}
                onWidthsChange={onColumnWidthsChange}
                extraColumn={extraColumn}
                tableLayout={tableLayout}
              />
              {isLastTablePage && trailingFitsLastTablePage && (
                <>
                  <DocumentBlocks blocks={afterBlocks} alignments={miniBoxAlignments} />
                  <ProposalTrailingContent
                    items={items}
                    commercialTerms={commercialTerms}
                    responsible={responsible}
                  />
                </>
              )}
              </div>
              {(pagePartsPreview || footer.length > 0) && (
                <div className="proposal-replica-template-footer">
                  {pagePartsPreview ? <TemplatePagePart preview={pagePartsPreview} kind="footer" pageIndex={pageIndex} onHeight={reportPartHeight} />
                    : <DocumentBlocks blocks={footer} alignments={miniBoxAlignments} />}
                </div>
              )}
              <span className="proposal-replica-page-number">{pageIndex + 1} / {pageCount}</span>
            </ReplicaPage>
          );
        })}
        {!trailingFitsLastTablePage && (
          <ReplicaPage preview={pagePartsPreview}>
            {(pagePartsPreview || header.length > 0) && (
              <div className="proposal-replica-template-header">
                {pagePartsPreview ? <TemplatePagePart preview={pagePartsPreview} kind="header" pageIndex={tablePages.length} onHeight={reportPartHeight} />
                  : <DocumentBlocks blocks={header} alignments={miniBoxAlignments} />}
              </div>
            )}
            <div className="proposal-replica-body">
            <DocumentBlocks blocks={afterBlocks} alignments={miniBoxAlignments} />
            <ProposalTrailingContent
              items={items}
              commercialTerms={commercialTerms}
              responsible={responsible}
            />
            </div>
            {(pagePartsPreview || footer.length > 0) && (
              <div className="proposal-replica-template-footer">
                {pagePartsPreview ? <TemplatePagePart preview={pagePartsPreview} kind="footer" pageIndex={tablePages.length} onHeight={reportPartHeight} />
                  : <DocumentBlocks blocks={footer} alignments={miniBoxAlignments} />}
              </div>
            )}
            <span className="proposal-replica-page-number">{pageCount} / {pageCount}</span>
          </ReplicaPage>
        )}
      </div>
    </section>
  );
}
