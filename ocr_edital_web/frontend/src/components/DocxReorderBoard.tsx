import { useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useDraggable,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent, DragOverEvent, DragStartEvent } from "@dnd-kit/core";
import {
  SortableContext,
  rectSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlignCenter,
  ChevronLeft,
  ChevronRight,
  GripVertical,
  Plus,
  RotateCcw,
  Table2,
  Trash2,
  Undo2,
} from "lucide-react";
import {
  createDocumentBlockOrder,
  insertDocumentBlockBefore,
  miniBoxNodes,
  moveDocumentBlock,
  reorderDocumentBlocks,
} from "../docxOrder";
import type {
  DocumentNode,
  DocxStructureResponse,
  GeneratedTableBlock,
  MiniBoxNode,
  MiniBoxTextAlign,
} from "../types";

const DOCUMENT_PAGE_ID = "docx-document-page";
const GENERATED_TABLE_DOCK_ID = "docx-generated-table-dock";

interface DocxReorderBoardProps {
  structure: DocxStructureResponse;
  nodes: DocumentNode[];
  blockOrder: string[];
  alignments: Record<string, MiniBoxTextAlign>;
  disabled?: boolean;
  onOrderChange: (order: string[]) => void;
  onOrderCommit: () => void;
  onAlignmentChange: (id: string, alignment: MiniBoxTextAlign) => void;
  onAlignmentsReset: (alignments: Record<string, MiniBoxTextAlign>) => void;
  renderPreview: (order: string[]) => ReactNode;
}

interface SortableDocumentBlockProps {
  id: string;
  content: string;
  generated: boolean;
  tone: number;
  position: number;
  total: number;
  disabled: boolean;
  alignment: MiniBoxTextAlign;
  onMove: (id: string, direction: -1 | 1) => void;
  onToggleAlignment: (id: string) => void;
  onDelete: (id: string) => void;
  onReturnToDock: () => void;
}

function ordersMatch(left: string[], right: string[]): boolean {
  return left.length === right.length
    && left.every((nodeId, index) => nodeId === right[index]);
}

function DocumentBlockContent({
  content,
  generated,
  alignment,
}: {
  content: string;
  generated: boolean;
  alignment: MiniBoxTextAlign;
}) {
  const label = generated ? "Tabela gerada" : (content.trim() || "Bloco vazio");
  return (
    <div
      className={`docx-mini-box-content${alignment === "center" ? " is-text-centered" : ""}`}
      title={label}
      style={generated ? undefined : { textAlign: alignment }}
    >
      {generated && <Table2 size={20} aria-hidden="true" />}
      <span>{`{${label}}`}</span>
    </div>
  );
}

function SortableDocumentBlock({
  id,
  content,
  generated,
  tone,
  position,
  total,
  disabled,
  alignment,
  onMove,
  onToggleAlignment,
  onDelete,
  onReturnToDock,
}: SortableDocumentBlockProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled });
  const style: CSSProperties = {
    // Sortable transforms may include scale when cards span different grid tracks.
    // Translation-only movement keeps the dragged card's dimensions unchanged.
    transform: CSS.Translate.toString(transform),
    transition: isDragging ? "none" : transition,
    willChange: isDragging ? "transform" : undefined,
  };

  return (
    <article
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      className={[
        "docx-mini-box",
        generated ? "is-generated-table" : `tone-${tone}`,
        isDragging ? "is-dragging" : "",
      ].filter(Boolean).join(" ")}
      style={style}
      role="listitem"
      aria-label={`${generated ? "Tabela gerada" : "Mini-box"}, posição ${position} de ${total}`}
      title={generated ? "Arraste para mover a tabela" : "Clique duas vezes e mantenha pressionado para arrastar"}
    >
      <div className="docx-mini-box-toolbar">
        <span className="docx-mini-box-index" aria-hidden="true">
          {String(position).padStart(2, "0")}
        </span>
        <div
          className="docx-mini-box-actions"
          onPointerDown={(event) => event.stopPropagation()}
          onTouchStart={generated ? (event) => event.stopPropagation() : undefined}
          onKeyDown={generated ? (event) => event.stopPropagation() : undefined}
        >
          {!generated && (
            <>
              <button
                type="button"
                className={`docx-order-button docx-align-button${alignment === "center" ? " is-active" : ""}`}
                onClick={() => onToggleAlignment(id)}
                disabled={disabled}
                aria-label={alignment === "center" ? "Remover centralização do mini-box" : "Centralizar texto do mini-box"}
                aria-pressed={alignment === "center"}
                title={alignment === "center" ? "Alinhar texto à esquerda" : "Centralizar texto"}
              >
                <AlignCenter size={16} />
              </button>
              <button
                type="button"
                className="docx-order-button docx-delete-button"
                onClick={() => onDelete(id)}
                disabled={disabled}
                aria-label={`Excluir mini-box ${position}`}
                title="Excluir mini-box"
              >
                <Trash2 size={15} />
              </button>
            </>
          )}
          <button
            type="button"
            className="docx-order-button"
            onClick={() => onMove(id, -1)}
            disabled={disabled || position === 1}
            aria-label={`Mover ${generated ? "tabela" : "mini-box"} para a posição anterior`}
            title="Posição anterior"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            className="docx-order-button"
            onClick={() => onMove(id, 1)}
            disabled={disabled || position === total}
            aria-label={`Mover ${generated ? "tabela" : "mini-box"} para a próxima posição`}
            title="Próxima posição"
          >
            <ChevronRight size={16} />
          </button>
          {generated && (
            <button
              type="button"
              className="docx-order-button"
              onClick={onReturnToDock}
              disabled={disabled}
              aria-label="Retornar tabela à área lateral"
              title="Retornar à área lateral"
            >
              <Undo2 size={16} />
            </button>
          )}
          {generated && (
            <button
              type="button"
              className="docx-drag-handle"
              disabled={disabled}
              aria-label="Arrastar tabela gerada"
              title="Arrastar tabela"
              {...attributes}
              {...listeners}
            >
              <GripVertical size={17} />
            </button>
          )}
        </div>
      </div>
      <DocumentBlockContent content={content} generated={generated} alignment={alignment} />
    </article>
  );
}

function GeneratedTableDock({
  block,
  docked,
  disabled,
  active,
  onInsert,
}: {
  block: GeneratedTableBlock;
  docked: boolean;
  disabled: boolean;
  active: boolean;
  onInsert: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef: setDraggableRef,
    transform,
    isDragging,
  } = useDraggable({
    // Only the visible table may register its document block ID.
    id: docked ? block.id : GENERATED_TABLE_DOCK_ID,
    disabled: disabled || !docked,
  });
  const { isOver, setNodeRef: setDroppableRef } = useDroppable({
    id: GENERATED_TABLE_DOCK_ID,
    disabled: disabled || docked,
  });
  const style: CSSProperties = {
    transform: CSS.Translate.toString(transform),
  };

  return (
    <aside
      ref={setDroppableRef}
      className={`docx-generated-table-dock${isOver ? " is-over" : ""}${active ? " is-active" : ""}`}
      aria-label="Área lateral da tabela gerada"
    >
      {docked ? (
        <article
          ref={setDraggableRef}
          {...attributes}
          {...listeners}
          className={`docx-mini-box is-generated-table is-docked${isDragging ? " is-dragging" : ""}`}
          style={style}
          aria-label="Tabela gerada na área lateral"
          title="Arraste para mover a tabela"
        >
          <div className="docx-mini-box-toolbar">
            <Table2 size={18} aria-hidden="true" />
            <div
              className="docx-mini-box-actions"
              onPointerDown={(event) => event.stopPropagation()}
              onTouchStart={(event) => event.stopPropagation()}
              onKeyDown={(event) => event.stopPropagation()}
            >
              <button
                type="button"
                className="docx-order-button"
                onClick={onInsert}
                disabled={disabled}
                aria-label="Inserir tabela no final do documento"
                title="Inserir no documento"
              >
                <Plus size={16} />
              </button>
              <button
                type="button"
                className="docx-drag-handle"
                disabled={disabled}
                aria-label="Arrastar tabela gerada para o documento"
                title="Arrastar tabela"
                {...attributes}
                {...listeners}
              >
                <GripVertical size={17} />
              </button>
            </div>
          </div>
          <DocumentBlockContent content={block.content} generated alignment="center" />
        </article>
      ) : (
        <div className="docx-generated-table-return" role="img" aria-label="Área de retorno da tabela">
          <Table2 size={24} aria-hidden="true" />
        </div>
      )}
    </aside>
  );
}

function DocumentPage({
  active,
  children,
}: {
  active: boolean;
  children: ReactNode;
}) {
  const { isOver, setNodeRef } = useDroppable({ id: DOCUMENT_PAGE_ID });
  return (
    <div
      ref={setNodeRef}
      className={`docx-document-page${isOver ? " is-over" : ""}${active ? " is-active" : ""}`}
      role="list"
    >
      {children}
    </div>
  );
}

export function DocxReorderBoard({
  structure,
  nodes,
  blockOrder,
  alignments,
  disabled = false,
  onOrderChange,
  onOrderCommit,
  onAlignmentChange,
  onAlignmentsReset,
  renderPreview,
}: DocxReorderBoardProps) {
  const [previewOrder, setPreviewOrder] = useState<string[] | null>(null);
  const previewOrderRef = useRef<string[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [tableDocked, setTableDocked] = useState(true);
  const [announcement, setAnnouncement] = useState("");
  const previewFrameRef = useRef<number | null>(null);
  const queuedPreviewRef = useRef<{ order: string[]; nodeId: string } | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 160, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const tableBlock = structure.generated_table_block;
  const tableId = tableBlock.id;
  const displayedOrder = previewOrder || blockOrder;
  // Keep the physical sortable grid stable while dnd-kit animates its positions.
  // The lightweight replica still follows displayedOrder in real time.
  const pageOrder = tableDocked
    ? blockOrder.filter((nodeId) => nodeId !== tableId)
    : blockOrder;
  const displayedPageOrder = tableDocked
    ? displayedOrder.filter((nodeId) => nodeId !== tableId)
    : displayedOrder;
  const miniBoxes = useMemo(() => miniBoxNodes(nodes), [nodes]);
  const miniBoxesById = useMemo(
    () => new Map(miniBoxes.map((node) => [node.id, node])),
    [miniBoxes],
  );
  const tonesById = useMemo(
    () => new Map(
      miniBoxNodes(structure.nodes).map((node, index) => [node.id, (index % 4) + 1]),
    ),
    [structure.nodes],
  );
  const originalOrder = useMemo(
    () => createDocumentBlockOrder(structure.nodes, tableId),
    [structure.nodes, tableId],
  );
  const originalAlignments = useMemo(
    () => Object.fromEntries(
      miniBoxNodes(structure.nodes).map((node) => [node.id, node.text_align]),
    ) as Record<string, MiniBoxTextAlign>,
    [structure.nodes],
  );
  const hasAlignmentChanges = Object.entries(originalAlignments).some(
    ([nodeId, alignment]) => alignments[nodeId] !== alignment,
  );
  const hasChanges = !tableDocked
    || !ordersMatch(blockOrder, originalOrder)
    || hasAlignmentChanges;

  useEffect(() => {
    if (previewFrameRef.current !== null) {
      window.cancelAnimationFrame(previewFrameRef.current);
      previewFrameRef.current = null;
    }
    queuedPreviewRef.current = null;
    setPreviewOrder(null);
    previewOrderRef.current = null;
    setActiveId(null);
    setTableDocked(true);
    setAnnouncement("");
  }, [structure.document_signature]);

  useEffect(() => () => {
    if (previewFrameRef.current !== null) {
      window.cancelAnimationFrame(previewFrameRef.current);
    }
  }, []);

  const commitOrder = (nextOrder: string[], message: string) => {
    onOrderChange(nextOrder);
    setAnnouncement(message);
    onOrderCommit();
  };

  const announcePosition = (candidateOrder: string[], nodeId: string) => {
    const visibleOrder = tableDocked
      ? candidateOrder.filter((candidateId) => candidateId !== tableId)
      : candidateOrder;
    const position = visibleOrder.indexOf(nodeId) + 1;
    if (position > 0) {
      setAnnouncement(`Bloco movido para a posição ${position}.`);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    const id = String(event.active.id);
    setActiveId(id);
    setPreviewOrder(blockOrder);
    previewOrderRef.current = blockOrder;
    if (id === tableId && tableDocked) {
      setAnnouncement("Tabela gerada selecionada.");
    } else {
      announcePosition(blockOrder, id);
    }
  };

  const handleDragOver = (event: DragOverEvent) => {
    const draggingId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : "";
    if (
      !overId
      || draggingId === overId
      || (draggingId === tableId && tableDocked)
      || !blockOrder.includes(overId)
    ) {
      return;
    }
    const candidate = reorderDocumentBlocks(blockOrder, draggingId, overId);
    if (ordersMatch(candidate, previewOrderRef.current || blockOrder)) return;

    previewOrderRef.current = candidate;
    queuedPreviewRef.current = { order: candidate, nodeId: draggingId };
    if (previewFrameRef.current !== null) return;

    previewFrameRef.current = window.requestAnimationFrame(() => {
      previewFrameRef.current = null;
      const queuedPreview = queuedPreviewRef.current;
      queuedPreviewRef.current = null;
      if (!queuedPreview) return;
      setPreviewOrder(queuedPreview.order);
      announcePosition(queuedPreview.order, queuedPreview.nodeId);
    });
  };

  const clearDragState = () => {
    if (previewFrameRef.current !== null) {
      window.cancelAnimationFrame(previewFrameRef.current);
      previewFrameRef.current = null;
    }
    queuedPreviewRef.current = null;
    setActiveId(null);
    setPreviewOrder(null);
    previewOrderRef.current = null;
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const draggingId = String(event.active.id);
    const overId = event.over ? String(event.over.id) : "";

    if (draggingId === tableId && tableDocked) {
      if (overId && overId !== GENERATED_TABLE_DOCK_ID) {
        const beforeId = blockOrder.includes(overId) ? overId : undefined;
        const nextOrder = insertDocumentBlockBefore(blockOrder, tableId, beforeId);
        setTableDocked(false);
        commitOrder(nextOrder, "Tabela inserida no documento.");
      }
      clearDragState();
      return;
    }

    if (draggingId === tableId && overId === GENERATED_TABLE_DOCK_ID) {
      const nextOrder = insertDocumentBlockBefore(blockOrder, tableId);
      setTableDocked(true);
      commitOrder(nextOrder, "Tabela retornada à área lateral.");
      clearDragState();
      return;
    }

    const previewedOrder = previewOrderRef.current;
    let nextOrder = previewedOrder || blockOrder;
    if (!previewedOrder && overId && blockOrder.includes(overId)) {
      nextOrder = reorderDocumentBlocks(nextOrder, draggingId, overId);
    } else if (overId === DOCUMENT_PAGE_ID) {
      nextOrder = tableDocked
        ? insertDocumentBlockBefore(nextOrder, draggingId, tableId)
        : insertDocumentBlockBefore(nextOrder, draggingId);
    }
    if (!ordersMatch(nextOrder, blockOrder)) {
      commitOrder(nextOrder, `Bloco movido para a posição ${nextOrder.indexOf(draggingId) + 1}.`);
    }
    clearDragState();
  };

  const handleDragCancel = () => {
    clearDragState();
    setAnnouncement("Reordenação cancelada.");
  };

  const handleMove = (nodeId: string, direction: -1 | 1) => {
    const visibleOrder = tableDocked
      ? blockOrder.filter((candidateId) => candidateId !== tableId)
      : blockOrder;
    const movedVisibleOrder = moveDocumentBlock(visibleOrder, nodeId, direction);
    if (movedVisibleOrder === visibleOrder) return;
    const nextOrder = tableDocked
      ? [...movedVisibleOrder, tableId]
      : movedVisibleOrder;
    commitOrder(nextOrder, `Bloco movido para a posição ${movedVisibleOrder.indexOf(nodeId) + 1}.`);
  };

  const toggleTextAlignment = (nodeId: string) => {
    const currentAlignment = alignments[nodeId] || originalAlignments[nodeId] || "left";
    const nextAlignment = currentAlignment === "center" ? "left" : "center";
    onAlignmentChange(nodeId, nextAlignment);
    setAnnouncement(
      nextAlignment === "center"
        ? "Texto do mini-box centralizado."
        : "Texto do mini-box alinhado à esquerda.",
    );
  };

  const deleteMiniBox = (nodeId: string) => {
    commitOrder(
      blockOrder.filter((candidateId) => candidateId !== nodeId),
      "Mini-box excluído da composição e da pré-visualização.",
    );
  };

  const insertTableAtEnd = () => {
    setTableDocked(false);
    commitOrder(
      insertDocumentBlockBefore(blockOrder, tableId),
      "Tabela inserida no final do documento.",
    );
  };

  const returnTableToDock = () => {
    setTableDocked(true);
    commitOrder(
      insertDocumentBlockBefore(blockOrder, tableId),
      "Tabela retornada à área lateral.",
    );
  };

  const restoreOriginalOrder = () => {
    setTableDocked(true);
    onAlignmentsReset(originalAlignments);
    commitOrder(originalOrder, "Ordem original restaurada.");
  };

  return (
    <section className="docx-reorder-workspace" aria-labelledby="docx-reorder-heading">
      <div className="docx-reorder-heading">
        <div>
          <h4 id="docx-reorder-heading">Composição visual do documento</h4>
          <span>{blockOrder.filter((nodeId) => nodeId !== tableId).length} mini-box(es) + tabela da proposta</span>
        </div>
        {hasChanges && (
          <button
            type="button"
            className="button button-secondary docx-reset-order"
            onClick={restoreOriginalOrder}
            disabled={disabled}
          >
            <RotateCcw size={16} />
            Restaurar ordem
          </button>
        )}
      </div>

      {structure.warnings.length > 0 && (
        <div className="docx-structure-warnings" role="status">
          {structure.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <div className="docx-document-stage" aria-busy={Boolean(activeId)}>
          <div className="docx-stage-column docx-blocks-column">
            <span className="docx-stage-label">Blocos gerados</span>
            <GeneratedTableDock
              block={tableBlock}
              docked={tableDocked}
              disabled={disabled}
              active={activeId === tableId}
              onInsert={insertTableAtEnd}
            />
          </div>
          <div className="docx-stage-column docx-organization-column">
            <span className="docx-stage-label">Organização</span>
            <SortableContext items={pageOrder} strategy={rectSortingStrategy}>
              <DocumentPage active={Boolean(activeId)}>
                {pageOrder.map((nodeId, index) => {
                  const generated = nodeId === tableId;
                  const node: MiniBoxNode | undefined = miniBoxesById.get(nodeId);
                  if (!generated && !node) return null;
                  return (
                    <SortableDocumentBlock
                      key={nodeId}
                      id={nodeId}
                      content={generated ? tableBlock.content : node?.content || ""}
                      generated={generated}
                      tone={tonesById.get(nodeId) || 1}
                      position={displayedPageOrder.indexOf(nodeId) + 1 || index + 1}
                      total={displayedPageOrder.length}
                      disabled={disabled}
                      alignment={generated
                        ? "center"
                        : alignments[nodeId] || node?.text_align || "left"}
                      onMove={handleMove}
                      onToggleAlignment={toggleTextAlignment}
                      onDelete={deleteMiniBox}
                      onReturnToDock={returnTableToDock}
                    />
                  );
                })}
              </DocumentPage>
            </SortableContext>
          </div>
          <div className="docx-stage-column docx-preview-column">
            <span className="docx-stage-label">Pré-visualização</span>
            {renderPreview(displayedOrder)}
          </div>
        </div>
      </DndContext>
      <p className="sr-only" aria-live="polite">{announcement}</p>
    </section>
  );
}
