import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, ArrowRight, Plus, Trash2, X } from "lucide-react";
import { createKanbanColumn, deleteKanbanColumn, getKanbanBoard, moveKanbanColumn, moveKanbanProposal, saveKanbanProposal, updateKanbanColumn } from "../api";
import type { KanbanColumn, KanbanProposal, KanbanProposalInput, UiMessage } from "../types";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

const emptyProposal: KanbanProposalInput = {
  column_id: "", portal: "", position_number: "", modality: "Pregão Eletrônico", agency_name: "",
  notice_number: "", uasg: "", pncp_control_number: "", opening_at: "",
  critical_deadline: "", internal_identifier: "", title: "", object_description: "",
  phase_status: "", priority: "normal", pending_documents: "", estimated_value: "",
  responsible: "", next_review_at: "", notes: "", source_link: "",
};

function positionClass(value: string) {
  if (String(value) === "1") return " position-first";
  if (String(value) === "2") return " position-second";
  if (String(value) === "3") return " position-third";
  return "";
}

export function ProposalFlowBlock() {
  const [columns, setColumns] = useState<KanbanColumn[]>([]);
  const [proposals, setProposals] = useState<KanbanProposal[]>([]);
  const [editing, setEditing] = useState<KanbanProposal | null>(null);
  const [draft, setDraft] = useState<KanbanProposalInput>(emptyProposal);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [syncStatus] = useState<"offline">("offline");

  const reload = async () => {
    const board = await getKanbanBoard();
    setColumns(board.columns);
    setProposals(board.proposals);
  };

  useEffect(() => { void reload().catch((error) => setMessage({ kind: "error", text: error.message })); }, []);
  const grouped = useMemo(() => new Map(columns.map((column) => [
    column.id,
    proposals
      .filter((proposal) => proposal.column_id === column.id)
      .sort((first, second) => {
        const firstPosition = Number(first.position_number) || Number.POSITIVE_INFINITY;
        const secondPosition = Number(second.position_number) || Number.POSITIVE_INFINITY;
        return firstPosition - secondPosition || first.title.localeCompare(second.title, "pt-BR");
      }),
  ])), [columns, proposals]);

  const beginCreate = (column: KanbanColumn) => {
    setEditing(null);
    setDraft({ ...emptyProposal, column_id: column.id, portal: column.name });
    setOpen(true);
  };
  const beginEdit = (proposal: KanbanProposal) => {
    setEditing(proposal);
    setDraft({ ...proposal });
    setOpen(true);
  };
  const change = (field: keyof KanbanProposalInput, value: string) => setDraft((current) => ({ ...current, [field]: value }));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await saveKanbanProposal(draft, editing?.id);
      await reload();
      setOpen(false);
      setMessage({ kind: "success", text: editing ? "Proposta atualizada." : "Proposta cadastrada." });
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Não foi possível salvar." });
    } finally { setBusy(false); }
  };

  const addColumn = async () => {
    const name = window.prompt("Nome da nova coluna:")?.trim();
    if (!name) return;
    try { await createKanbanColumn(name); await reload(); }
    catch (error) { setMessage({ kind: "error", text: error instanceof Error ? error.message : "Não foi possível criar a coluna." }); }
  };

  const rename = async (column: KanbanColumn) => {
    const name = window.prompt("Novo nome da coluna:", column.name)?.trim();
    if (!name || name === column.name) return;
    try { await updateKanbanColumn(column.id, { name }); await reload(); }
    catch (error) { setMessage({ kind: "error", text: error instanceof Error ? error.message : "Não foi possível renomear." }); }
  };

  const remove = async (column: KanbanColumn) => {
    if (!window.confirm(`Excluir a coluna “${column.name}”? Esta ação só será aceita se ela estiver vazia.`)) return;
    try { await deleteKanbanColumn(column.id); await reload(); }
    catch (error) { setMessage({ kind: "error", text: error instanceof Error ? error.message : "Não foi possível excluir." }); }
  };

  const drop = async (event: React.DragEvent, column: KanbanColumn) => {
    event.preventDefault();
    const id = event.dataTransfer.getData("text/proposal-id");
    if (!id) return;
    setProposals((current) => current.map((item) => item.id === id ? { ...item, column_id: column.id, portal: column.name } : item));
    try { await moveKanbanProposal(id, column.id); }
    catch (error) { await reload(); setMessage({ kind: "error", text: error instanceof Error ? error.message : "Não foi possível mover." }); }
  };

  return <section className="workspace-section proposal-flow" aria-labelledby="flow-heading">
    <div className="section-heading flow-heading">
      <div><span className="section-kicker">Bloco 06</span><h2 id="flow-heading">Fluxo de propostas</h2><p>Kanban por portal, com histórico de movimentação e persistência local.</p></div>
      <div className="flow-actions"><span className="sync-badge is-offline">Offline · sincronização manual</span><button className="button button-primary" type="button" onClick={() => void addColumn()}><Plus size={17}/> Nova coluna</button></div>
    </div>
    <StatusMessage message={message}/>
    <div className="proposal-kanban" aria-label="Kanban de propostas">
      {columns.map((column, index) => <article className="proposal-kanban-column" key={column.id} onDragOver={(event) => event.preventDefault()} onDrop={(event) => void drop(event, column)}>
        <header style={{ borderTopColor: column.color }}>
          <button className="column-title" type="button" onClick={() => void rename(column)} title="Renomear coluna">{column.name}</button>
          <span>{grouped.get(column.id)?.length || 0}</span>
          <div className="column-controls">
            <button disabled={index === 0} onClick={() => void moveKanbanColumn(column.id, "left").then(reload)} aria-label="Mover coluna para esquerda"><ArrowLeft size={14}/></button>
            <button disabled={index === columns.length - 1} onClick={() => void moveKanbanColumn(column.id, "right").then(reload)} aria-label="Mover coluna para direita"><ArrowRight size={14}/></button>
            <button onClick={() => void remove(column)} aria-label="Excluir coluna"><Trash2 size={14}/></button>
          </div>
        </header>
        <div className="proposal-card-list">
          {(grouped.get(column.id) || []).map((proposal) => <button type="button" draggable className={`proposal-flow-card${positionClass(proposal.position_number)}`} key={proposal.id} onDragStart={(event) => event.dataTransfer.setData("text/proposal-id", proposal.id)} onClick={() => beginEdit(proposal)}>
            <strong>{proposal.title}</strong>
            <span><b>Portal:</b> {proposal.portal}</span>
            <span><b>Posição:</b> {proposal.position_number || "Não informada"}</span>
            <span><b>Nº do pregão:</b> {proposal.notice_number || "Não informado"}</span>
            <span><b>UASG:</b> {proposal.uasg || "Não informada"}</span>
            <span><b>Abertura:</b> {proposal.opening_at ? new Date(proposal.opening_at).toLocaleString("pt-BR") : "Não informada"}</span>
          </button>)}
          <button className="add-proposal-card" type="button" onClick={() => beginCreate(column)}><Plus size={16}/> Nova proposta</button>
        </div>
      </article>)}
    </div>
    <Modal open={open} title={editing ? "Editar proposta" : "Nova proposta"} onClose={() => setOpen(false)}>
      <form className="proposal-editor" onSubmit={submit}>
        <button className="modal-x" type="button" onClick={() => setOpen(false)} aria-label="Fechar"><X size={18}/></button>
        <label className="wide">Título<input required value={draft.title} onChange={(e) => change("title", e.target.value)} placeholder="Informe o título da proposta"/></label>
        <label>Portal<select value={draft.column_id} onChange={(e) => change("column_id", e.target.value)}>{columns.map((column) => <option key={column.id} value={column.id}>{column.name}</option>)}</select></label>
        <label>Posição<input type="number" min="1" step="1" value={draft.position_number} onChange={(e) => change("position_number", e.target.value)} placeholder="1, 2, 3..."/></label>
        <label>Número do pregão<input value={draft.notice_number} onChange={(e) => change("notice_number", e.target.value)} placeholder="Ex.: 90001/2026"/></label>
        <label>UASG<input value={draft.uasg} onChange={(e) => change("uasg", e.target.value)} placeholder="Informe o número da UASG"/></label>
        <label className="wide">Data e hora de abertura<input type="datetime-local" value={draft.opening_at} onChange={(e) => change("opening_at", e.target.value)}/></label>
        <div className="form-actions wide"><button className="button button-primary" disabled={busy} type="submit">Salvar</button><button className="button button-secondary" type="button" onClick={() => setOpen(false)}>Cancelar</button></div>
      </form>
    </Modal>
  </section>;
}
