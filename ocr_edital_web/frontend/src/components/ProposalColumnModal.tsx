import { useRef, useState } from "react";
import { Minus, Plus, RotateCcw } from "lucide-react";
import type { ProposalExtraColumn, ProposalItem, ProposalColumnKey, ProposalTableLayout, ProposalColumnWidths } from "../types";
import { proposalCellValue, proposalColumns, normalizeProposalColumnWidths, defaultProposalColumnWidths } from "../proposalPreviewLayout";
import { ColumnResizeHandle } from "./ProposalLivePreview";
import { calculateItemTotal, sanitizeMoneyInput } from "../utils";
import { Modal } from "./Modal";

interface Props {
  items: ProposalItem[];
  column: ProposalExtraColumn | null;
  layout?: ProposalTableLayout | null;
  widths: ProposalColumnWidths;
  onSave: (items: ProposalItem[], layout: ProposalTableLayout, widths: ProposalColumnWidths) => void;
  onClose: () => void;
}

export function ProposalColumnModal({ items, column, layout, widths, onSave, onClose }: Props) {
  const [draftWidths, setDraftWidths] = useState<ProposalColumnWidths>(() => ({
    ...widths, ...(widths.extra_column ? { custom_legacy: widths.extra_column } : {}),
  }));
  const [draftItems, setDraftItems] = useState(() => items.map((item) => ({ ...item })));
  const [draft, setDraft] = useState<ProposalTableLayout>(() => layout
    ? { columns: layout.columns.map((entry) => ({ ...entry })), custom_values: structuredClone(layout.custom_values) }
    : {
      columns: proposalColumns(items.some((item) => Boolean(item.lote?.trim())), column)
        .map((entry) => entry.key === "extra_column" ? { ...entry, key: "custom_legacy" } : { ...entry }),
      custom_values: column ? { custom_legacy: [...column.values] } : {},
    });
  const [removing, setRemoving] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const tableRef = useRef<HTMLDivElement>(null);
  const showLot = draftItems.some((item) => Boolean(item.lote?.trim()));
  const normalizedWidths = normalizeProposalColumnWidths(draftWidths, showLot, null, draft);
  const tableWidth = Math.max(900, draft.columns.length * 128);
  const addColumn = () => {
    const key: ProposalColumnKey = `custom_${crypto.randomUUID().replaceAll("-", "")}`;
    setDraftWidths({ ...normalizedWidths, [key]: 100 / draft.columns.length });
    setDraft((current) => ({ columns: [...current.columns, { key, label: `Coluna ${current.columns.length + 1}` }],
      custom_values: { ...current.custom_values, [key]: items.map(() => "") } }));
    setRemoving(false);
    requestAnimationFrame(() => {
      const input = tableRef.current?.querySelector<HTMLInputElement>(`input[data-column="${key}"]`);
      input?.focus(); input?.select(); input?.scrollIntoView({ block: "nearest", inline: "nearest" });
    });
  };
  const removeColumn = (key: ProposalColumnKey) => {
    if (draft.columns.length <= 1) return;
    const label = draft.columns.find((entry) => entry.key === key)?.label;
    setDraft((current) => {
      const values = { ...current.custom_values }; delete values[key];
      return { columns: current.columns.filter((entry) => entry.key !== key), custom_values: values };
    });
    setRemoving(false);
    setAnnouncement(`Coluna ${label} removida do rascunho.`);
  };
  const updateCell = (row: number, key: ProposalColumnKey, value: string) => {
    if (key.startsWith("custom_")) {
      setDraft((current) => ({ ...current, custom_values: { ...current.custom_values,
        [key]: draftItems.map((_, index) => index === row ? value : current.custom_values[key]?.[index] || "") } }));
      return;
    }
    const numeric = ["lote", "item", "quantidade", "valor_unitario"].includes(key);
    setDraftItems((current) => current.map((item, index) => {
      if (index !== row) return item;
      const next = { ...item, [key]: key === "item" || key === "lote"
        ? value.replace(/\D/g, "") : numeric ? sanitizeMoneyInput(value) : value };
      if (key === "quantidade" || key === "valor_unitario") next.valor_total = calculateItemTotal(next.quantidade, next.valor_unitario);
      return next;
    }));
  };
  return (
    <Modal open title="Editar tabela" onClose={onClose} wide className="proposal-table-editor">
      <form onSubmit={(event) => { event.preventDefault(); onSave(draftItems, {
        ...draft, columns: draft.columns.map((entry) => ({ ...entry, label: entry.label.trim() })),
      }, normalizedWidths); }}>
        <div ref={tableRef} className={`proposal-table-editor-scroll${removing ? " is-removing" : ""}`}>
          <table className="proposal-table-editor-grid" style={{ width: tableWidth + 54 }}>
            <colgroup>{draft.columns.map(({ key }) => <col key={key} style={{ width: tableWidth * (normalizedWidths[key] || 0) / 100 }} />)}<col className="is-add" /></colgroup>
            <thead><tr>
              {draft.columns.map(({ key, label }, index) => <th key={key}>
                {removing ? <button type="button" className="proposal-table-remove-target" onClick={() => removeColumn(key)}
                  aria-label={`Remover coluna ${index + 1}: ${label}`}><Minus size={15} />{label || `Coluna ${index + 1}`}</button>
                  : <input data-column={key} autoFocus={index === 0} required maxLength={120} value={label}
                    aria-label={`Título da coluna ${index + 1}`}
                    onChange={(event) => setDraft((current) => ({ ...current, columns: current.columns.map((entry) =>
                      entry.key === key ? { ...entry, label: event.target.value } : entry) }))} />}
                {!removing && index < draft.columns.length - 1 && <ColumnResizeHandle
                  left={key} right={draft.columns[index + 1].key} widths={normalizedWidths}
                  showLot={showLot} tableLayout={draft} onChange={setDraftWidths} />}
              </th>)}
              <th className="proposal-table-add-cell"><button className="proposal-table-add" type="button" onClick={addColumn}
                disabled={draft.columns.length >= 24} aria-label="Adicionar coluna" title="Adicionar coluna"><Plus size={28} /></button></th>
            </tr></thead>
            <tbody>{draftItems.map((item, row) => <tr key={row}>
              {draft.columns.map(({ key, label }) => <td key={key}>
                <textarea rows={key === "descricao" ? 4 : 2} value={proposalCellValue(item, row, key, draft)}
                  aria-label={`${label}, linha ${row + 1}`} readOnly={key === "valor_total"}
                  title={key === "valor_total" ? "Total calculado pela quantidade e valor unitário" : undefined}
                  maxLength={key === "marca" ? 120 : key.startsWith("custom_") ? 5000 : undefined}
                  inputMode={["lote", "item", "quantidade", "valor_unitario"].includes(key) ? "decimal" : "text"}
                  onChange={(event) => updateCell(row, key, event.target.value)} />
              </td>)}<td className="proposal-table-add-cell" />
            </tr>)}</tbody>
          </table>
        </div>
        <span className="sr-only" role="status">{announcement}</span>
        <div className="proposal-table-editor-actions">
          <button type="button" className="button button-secondary" title="Restaurar largura das colunas"
            aria-label="Restaurar largura das colunas" onClick={() => setDraftWidths(defaultProposalColumnWidths(showLot, null, draft))}><RotateCcw size={20} /></button>
          <button type="button" className={`proposal-table-remove${removing ? " is-active" : ""}`}
            onClick={() => setRemoving((current) => !current)} disabled={draft.columns.length <= 1}
            aria-pressed={removing} aria-label="Remover coluna" title="Remover coluna"><Minus size={24} /></button>
          <button type="button" className="button button-secondary" onClick={onClose}>Cancelar</button>
          <button type="submit" className="button button-primary" disabled={draft.columns.some(({ label }) => !label.trim())}>Salvar</button>
        </div>
      </form>
    </Modal>
  );
}
