import { useMemo } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent } from "react";
import { FileText, RotateCcw } from "lucide-react";
import { createReplicaDocumentBlocks, withoutTemplateHeader } from "../docxOrder";
import type { ReplicaDocumentBlock } from "../docxOrder";
import {
  PREVIEW_PAGE_LINE_CAPACITY,
  PREVIEW_TABLE_HEADER_LINES,
  defaultProposalColumnWidths,
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
  Responsible,
} from "../types";
import { formatCents, parseMoneyToCents } from "../utils";

interface ProposalLivePreviewProps {
  nodes: DocumentNode[];
  blockOrder: string[];
  generatedTable: GeneratedTableBlock;
  items: ProposalItem[];
  commercialTerms: CommercialTerms;
  responsible?: Responsible;
  miniBoxAlignments: Record<string, MiniBoxTextAlign>;
  columnWidths: ProposalColumnWidths;
  onColumnWidthsChange: (widths: ProposalColumnWidths) => void;
}

function proposalTotal(items: ProposalItem[]): string {
  const cents = items.reduce((total, item) => {
    const itemCents = parseMoneyToCents(item.valor_total || "");
    return total + (itemCents || 0n);
  }, 0n);
  return formatCents(cents);
}

function columnValue(row: ProposalRowFragment, key: ProposalColumnKey): string {
  if (key === "descricao") return row.description;
  if (row.continuation) return "";
  if (key === "unidade") return String(row.item.unidade || "UND");
  return String(row.item[key] || "");
}

function ColumnResizeHandle({
  left,
  right,
  widths,
  showLot,
  onChange,
}: {
  left: ProposalColumnKey;
  right: ProposalColumnKey;
  widths: ProposalColumnWidths;
  showLot: boolean;
  onChange: (widths: ProposalColumnWidths) => void;
}) {
  const resizeBy = (deltaPercent: number) => {
    onChange(resizeAdjacentProposalColumns(widths, showLot, left, right, deltaPercent));
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
        resizeAdjacentProposalColumns(initialWidths, showLot, left, right, deltaPercent),
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
}: {
  rows: ProposalRowFragment[];
  columns: ProposalColumnDefinition[];
  widths: ProposalColumnWidths;
  showLot: boolean;
  onWidthsChange: (widths: ProposalColumnWidths) => void;
}) {
  return (
    <div className="proposal-replica-table-wrap">
      <table className="proposal-replica-table">
        <colgroup>
          {columns.map((column) => (
            <col key={column.key} style={{ width: `${widths[column.key] || 0}%` }} />
          ))}
        </colgroup>
        <thead>
          <tr>
            {columns.map((column, index) => (
              <th key={column.key}>
                {column.label}
                {index < columns.length - 1 && (
                  <ColumnResizeHandle
                    left={column.key}
                    right={columns[index + 1].key}
                    widths={widths}
                    showLot={showLot}
                    onChange={onWidthsChange}
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
}: ProposalLivePreviewProps) {
  const showLot = items.some((item) => Boolean(String(item.lote || "").trim()));
  const columns = proposalColumns(showLot);
  const normalizedWidths = normalizeProposalColumnWidths(columnWidths, showLot);
  const blocks = withoutTemplateHeader(
    createReplicaDocumentBlocks(nodes, blockOrder, generatedTable),
  );
  const tableIndex = blocks.findIndex((block) => block.type === "GENERATED_TABLE");
  const beforeBlocks = tableIndex >= 0 ? blocks.slice(0, tableIndex) : blocks;
  const afterBlocks = tableIndex >= 0 ? blocks.slice(tableIndex + 1) : [];
  const firstPageLines = Math.max(
    2,
    PREVIEW_PAGE_LINE_CAPACITY
      - PREVIEW_TABLE_HEADER_LINES
      - documentBlocksLineCost(beforeBlocks),
  );
  const tablePages = useMemo(
    () => paginateProposalRows(items, normalizedWidths, showLot, firstPageLines),
    [firstPageLines, items, normalizedWidths, showLot],
  );
  const lastTablePage = tablePages[tablePages.length - 1];
  const finalContentLines = trailingLineCost(afterBlocks, responsible);
  const trailingFitsLastTablePage = lastTablePage.remainingLines >= finalContentLines;
  const pageCount = tablePages.length + (trailingFitsLastTablePage ? 0 : 1);
  const defaultWidths = defaultProposalColumnWidths(showLot);
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
        {hasCustomWidths && (
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
            <article className="proposal-replica-page" key={`page-${pageIndex + 1}`}>
              {pageIndex === 0 && (
                <DocumentBlocks blocks={beforeBlocks} alignments={miniBoxAlignments} />
              )}
              <ReplicaTable
                rows={page.rows}
                columns={columns}
                widths={normalizedWidths}
                showLot={showLot}
                onWidthsChange={onColumnWidthsChange}
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
              <span className="proposal-replica-page-number">{pageIndex + 1} / {pageCount}</span>
            </article>
          );
        })}
        {!trailingFitsLastTablePage && (
          <article className="proposal-replica-page">
            <DocumentBlocks blocks={afterBlocks} alignments={miniBoxAlignments} />
            <ProposalTrailingContent
              items={items}
              commercialTerms={commercialTerms}
              responsible={responsible}
            />
            <span className="proposal-replica-page-number">{pageCount} / {pageCount}</span>
          </article>
        )}
      </div>
    </section>
  );
}
