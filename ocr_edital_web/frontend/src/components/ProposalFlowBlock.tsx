import { useEffect, useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  CalendarClock,
  Hash,
  MapPin,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import {
  createKanbanColumn,
  deleteKanbanColumn,
  deleteKanbanProposal,
  getKanbanBoard,
  moveKanbanColumn,
  moveKanbanProposal,
  saveKanbanProposal,
  updateKanbanColumn,
} from "../api";
import type { KanbanColumn, KanbanProposal, KanbanProposalInput, UiMessage } from "../types";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

const emptyProposal: KanbanProposalInput = {
  column_id: "",
  portal: "",
  position_number: "",
  modality: "Pregao Eletronico",
  agency_name: "",
  notice_number: "",
  uasg: "",
  pncp_control_number: "",
  opening_at: "",
  critical_deadline: "",
  internal_identifier: "",
  title: "",
  object_description: "",
  phase_status: "",
  priority: "normal",
  pending_documents: "",
  estimated_value: "",
  responsible: "",
  next_review_at: "",
  notes: "",
  source_link: "",
};

function positionClass(value: string) {
  if (String(value) === "1") return " position-first";
  if (String(value) === "2") return " position-second";
  if (String(value) === "3") return " position-third";
  return "";
}

function positionSortValue(value: string) {
  const position = Number(value);
  return Number.isFinite(position) && position > 0 ? position : Number.POSITIVE_INFINITY;
}

function shortText(value: string, limit = 132) {
  const text = String(value || "").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit - 3).trimEnd()}...`;
}

function formatOpening(value: string) {
  if (!value) return "Abertura nao informada";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return `Abertura em ${date.toLocaleString("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  })}`;
}

interface ProposalFlowBlockProps {
  onBack?: () => void;
  active?: boolean;
}

export function ProposalFlowBlock({ onBack, active = true }: ProposalFlowBlockProps) {
  const [columns, setColumns] = useState<KanbanColumn[]>([]);
  const [proposals, setProposals] = useState<KanbanProposal[]>([]);
  const [editing, setEditing] = useState<KanbanProposal | null>(null);
  const [draft, setDraft] = useState<KanbanProposalInput>(emptyProposal);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);

  const reload = async () => {
    const board = await getKanbanBoard();
    setColumns(board.columns);
    setProposals(board.proposals);
  };

  useEffect(() => {
    if (active) void reload().catch((error) => setMessage({ kind: "error", text: error.message }));
  }, [active]);

  const grouped = useMemo(
    () =>
      new Map(
        columns.map((column) => [
          column.id,
          proposals
            .filter((proposal) => proposal.column_id === column.id)
            .sort((first, second) => {
              return positionSortValue(first.position_number) - positionSortValue(second.position_number)
                || first.title.localeCompare(second.title, "pt-BR");
            }),
        ]),
      ),
    [columns, proposals],
  );

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

  const change = (field: keyof KanbanProposalInput, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await saveKanbanProposal(draft, editing?.id);
      await reload();
      window.dispatchEvent(new Event("toth:business-updated"));
      setOpen(false);
      setMessage({ kind: "success", text: editing ? "Proposta atualizada." : "Proposta cadastrada." });
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel salvar." });
    } finally {
      setBusy(false);
    }
  };

  const addColumn = async () => {
    const name = window.prompt("Nome da nova coluna:")?.trim();
    if (!name) return;
    try {
      await createKanbanColumn(name);
      await reload();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel criar a coluna." });
    }
  };

  const rename = async (column: KanbanColumn) => {
    const name = window.prompt("Novo nome da coluna:", column.name)?.trim();
    if (!name || name === column.name) return;
    try {
      await updateKanbanColumn(column.id, { name });
      await reload();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel renomear." });
    }
  };

  const remove = async (column: KanbanColumn) => {
    if (!window.confirm(`Excluir a coluna "${column.name}"? Esta acao so sera aceita se ela estiver vazia.`)) return;
    try {
      await deleteKanbanColumn(column.id);
      await reload();
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel excluir." });
    }
  };

  const removeProposal = async (proposal: KanbanProposal) => {
    if (!window.confirm(`Excluir o cartao "${proposal.title}"?`)) return;
    setProposals((current) => current.filter((item) => item.id !== proposal.id));
    try {
      await deleteKanbanProposal(proposal.id);
      await reload();
      window.dispatchEvent(new Event("toth:business-updated"));
      setMessage({ kind: "success", text: "Cartao excluido." });
    } catch (error) {
      await reload();
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel excluir o cartao." });
    }
  };

  const editProposalPosition = async (proposal: KanbanProposal) => {
    const answer = window.prompt(
      "Informe a posicao do cartao. Deixe em branco para remover:",
      proposal.position_number ? String(proposal.position_number) : "",
    );
    if (answer === null) return;
    const value = answer.trim();
    if (value && (!/^\d+$/.test(value) || Number(value) < 1)) {
      window.alert("A posicao deve ser um numero inteiro maior que zero.");
      return;
    }
    const updated: KanbanProposalInput = { ...proposal, position_number: value };
    setProposals((current) => current.map((item) => item.id === proposal.id ? { ...item, position_number: value } : item));
    try {
      await saveKanbanProposal(updated, proposal.id);
      await reload();
      window.dispatchEvent(new Event("toth:business-updated"));
      setMessage({ kind: "success", text: value ? "Posicao atualizada." : "Posicao removida." });
    } catch (error) {
      await reload();
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel atualizar a posicao." });
    }
  };

  const moveColumn = async (column: KanbanColumn, direction: "left" | "right") => {
    try {
      await moveKanbanColumn(column.id, direction);
      await reload();
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível mover a coluna.",
      });
    }
  };

  const drop = async (event: React.DragEvent, column: KanbanColumn) => {
    event.preventDefault();
    const id = event.dataTransfer.getData("text/proposal-id");
    if (!id) return;
    setProposals((current) =>
      current.map((item) => (item.id === id ? { ...item, column_id: column.id, portal: column.name } : item)),
    );
    try {
      await moveKanbanProposal(id, column.id);
    } catch (error) {
      await reload();
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Nao foi possivel mover." });
    }
  };

  return (
    <section className="workspace-section proposal-flow" aria-labelledby="flow-heading">
      <div className="section-heading flow-heading">
        <div>
          <span className="section-kicker">Bloco 04 - Classificacao</span>
          <h2 id="flow-heading">Classificacoes por portal</h2>
          <p>Kanban por portal, com historico de movimentacao e persistencia local.</p>
        </div>
        <div className="flow-actions">
          <span className="sync-badge is-offline">Offline - sincronizacao manual</span>
          {onBack ? (
            <button className="button button-secondary" type="button" onClick={onBack}>
              <ArrowLeft size={17} /> Voltar para Negocios
            </button>
          ) : null}
          <button className="button button-primary" type="button" onClick={() => void addColumn()}>
            <Plus size={17} /> Nova coluna
          </button>
        </div>
      </div>

      <StatusMessage message={message} />

      <div className="proposal-kanban" aria-label="Kanban de propostas">
        {columns.map((column, index) => {
          const columnProposals = grouped.get(column.id) || [];
          return (
            <article
              className="proposal-kanban-column"
              key={column.id}
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => void drop(event, column)}
            >
              <header style={{ borderTopColor: column.color }}>
                <div>
                  <button className="column-title" type="button" onClick={() => void rename(column)} title="Renomear coluna">
                    {column.name}
                  </button>
                  <p>Portal de origem</p>
                </div>
                <span>{columnProposals.length}</span>
                <div className="column-controls">
                  <button
                    disabled={index === 0}
                    onClick={() => void moveColumn(column, "left")}
                    aria-label="Mover coluna para esquerda"
                  >
                    <ArrowLeft size={14} />
                  </button>
                  <button
                    disabled={index === columns.length - 1}
                    onClick={() => void moveColumn(column, "right")}
                    aria-label="Mover coluna para direita"
                  >
                    <ArrowRight size={14} />
                  </button>
                  <button onClick={() => void remove(column)} aria-label="Excluir coluna">
                    <Trash2 size={14} />
                  </button>
                </div>
              </header>

              <div className="proposal-card-list">
                {columnProposals.map((proposal) => (
                  <article
                    draggable
                    className={`proposal-flow-card${positionClass(proposal.position_number)}`}
                    key={proposal.id}
                    onDragStart={(event) => event.dataTransfer.setData("text/proposal-id", proposal.id)}
                  >
                    <button className="proposal-flow-card-main" type="button" onClick={() => beginEdit(proposal)}>
                      <div className="proposal-flow-card-topline">
                        <span className="source-label">{proposal.portal || "PNCP"}</span>
                        <span className="urgency-label is-neutral">{proposal.phase_status || "Classificacao"}</span>
                      </div>
                      <div className="proposal-flow-card-reference">
                        <strong>{proposal.modality || "Modalidade nao informada"}</strong>
                        <span>{proposal.notice_number || proposal.pncp_control_number || "Pregao nao informado"}</span>
                      </div>
                      <h3 title={proposal.title || proposal.object_description}>
                        {shortText(proposal.title || proposal.object_description || "Objeto da proposta nao informado")}
                      </h3>
                      <div className="proposal-flow-card-meta">
                        <span title={proposal.agency_name}>
                          <Building2 size={14} aria-hidden="true" />
                          {proposal.agency_name || "Orgao nao informado"}
                        </span>
                        <span>
                          <MapPin size={14} aria-hidden="true" />
                          {proposal.portal || "Portal nao informado"}
                        </span>
                        <span>
                          <CalendarClock size={14} aria-hidden="true" />
                          {formatOpening(proposal.opening_at)}
                        </span>
                      </div>
                      <div className="proposal-flow-tags">
                        <span>{proposal.modality || "Sem modalidade"}</span>
                        <button
                          className="proposal-position-button"
                          type="button"
                          title="Definir posicao"
                          aria-label={`Posicao atual: ${proposal.position_number || "nao definida"}. Editar posicao`}
                          onClick={(event) => {
                            event.stopPropagation();
                            void editProposalPosition(proposal);
                          }}
                        >
                          Posicao: <strong>{proposal.position_number || "definir"}</strong>
                        </button>
                        <span>{proposal.priority || "normal"}</span>
                        {proposal.uasg ? (
                          <span>
                            <Hash size={10} aria-hidden="true" /> UASG {proposal.uasg}
                          </span>
                        ) : null}
                      </div>
                    </button>
                    <button
                      className="proposal-flow-delete"
                      type="button"
                      title="Excluir cartao"
                      aria-label={`Excluir cartao ${proposal.title}`}
                      onClick={() => void removeProposal(proposal)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </article>
                ))}
                <button className="add-proposal-card" type="button" onClick={() => beginCreate(column)}>
                  <Plus size={16} /> Nova proposta
                </button>
              </div>
            </article>
          );
        })}
      </div>

      <Modal open={open} title={editing ? "Editar proposta" : "Nova proposta"} onClose={() => setOpen(false)}>
        <form className="proposal-editor" onSubmit={submit}>
          <button className="modal-x" type="button" onClick={() => setOpen(false)} aria-label="Fechar">
            <X size={18} />
          </button>
          <label className="wide">
            Titulo
            <input required value={draft.title} onChange={(event) => change("title", event.target.value)} placeholder="Informe o titulo da proposta" />
          </label>
          <label>
            Portal
            <select value={draft.column_id} onChange={(event) => change("column_id", event.target.value)}>
              {columns.map((column) => (
                <option key={column.id} value={column.id}>
                  {column.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Posicao
            <input type="number" min="1" step="1" value={draft.position_number} onChange={(event) => change("position_number", event.target.value)} placeholder="1, 2, 3..." />
          </label>
          <label>
            Numero do pregao
            <input value={draft.notice_number} onChange={(event) => change("notice_number", event.target.value)} placeholder="Ex.: 90001/2026" />
          </label>
          <label>
            UASG
            <input value={draft.uasg} onChange={(event) => change("uasg", event.target.value)} placeholder="Informe o numero da UASG" />
          </label>
          <label className="wide">
            Data e hora de abertura
            <input type="datetime-local" value={draft.opening_at} onChange={(event) => change("opening_at", event.target.value)} />
          </label>
          <div className="form-actions wide">
            <button className="button button-primary" disabled={busy} type="submit">
              Salvar
            </button>
            <button className="button button-secondary" type="button" onClick={() => setOpen(false)}>
              Cancelar
            </button>
          </div>
        </form>
      </Modal>
    </section>
  );
}
