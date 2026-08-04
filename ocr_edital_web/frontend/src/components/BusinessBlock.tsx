import {
  Archive,
  ArrowDownUp,
  Building2,
  CalendarClock,
  Check,
  CheckSquare2,
  ChevronRight,
  ClipboardList,
  ExternalLink,
  Eye,
  FileArchive,
  FileText,
  Filter,
  Fullscreen,
  Grid3X3,
  Link2,
  List,
  LoaderCircle,
  MapPin,
  Maximize2,
  MoreHorizontal,
  PackageSearch,
  Pencil,
  Plus,
  Search,
  Star,
  Table2,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addBusinessTask,
  getBusiness,
  importBusiness,
  listBusinesses,
  moveBusiness,
  updateBusiness,
  updateBusinessTask,
} from "../api";
import type {
  Business,
  BusinessDetail,
  BusinessStage,
  Responsible,
} from "../types";
import { Modal } from "./Modal";

const STAGES: Array<{
  id: BusinessStage;
  label: string;
  description: string;
}> = [
  {
    id: "oportunidade",
    label: "Oportunidade",
    description: "Identificada e em avaliação inicial",
  },
  {
    id: "qualificacao",
    label: "Qualificação",
    description: "Análise técnica, comercial e documental",
  },
  {
    id: "disputa",
    label: "Disputa",
    description: "Participação confirmada",
  },
  {
    id: "classificacao",
    label: "Classificação",
    description: "Resultado e posicionamento",
  },
  {
    id: "contrato",
    label: "Contrato",
    description: "Formalização e execução",
  },
];

type BusinessView = "kanban" | "list" | "table";
type DetailTab = "dados" | "itens" | "tarefas" | "documentos" | "arquivos" | "historico";

interface BusinessFilters {
  keyword: string;
  modalidade: string;
  plataforma: string;
  aberturaInicial: string;
  aberturaFinal: string;
  etapa: string;
  situacao: string;
  tags: string;
}

const EMPTY_FILTERS: BusinessFilters = {
  keyword: "",
  modalidade: "",
  plataforma: "",
  aberturaInicial: "",
  aberturaFinal: "",
  etapa: "",
  situacao: "",
  tags: "",
};

const STAGE_INDEX = Object.fromEntries(
  STAGES.map((stage, index) => [stage.id, index]),
) as Record<BusinessStage, number>;

function parseDate(value: string) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatDateTime(value: string) {
  const date = parseDate(value);
  if (!date) return "Data não informada";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function formatCurrency(value: string) {
  if (!value) return "Não informado";
  const number = Number(value.replace(",", "."));
  if (!Number.isFinite(number)) return value;
  return number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function openingLabel(value: string) {
  const date = parseDate(value);
  if (!date) return "Abertura não informada";
  const day = new Intl.DateTimeFormat("pt-BR").format(date);
  const time = new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
  return `Abertura em ${day} às ${time}`;
}

function urgency(business: Business) {
  const date = parseDate(business.abertura || business.encerramento);
  if (!date) return { label: "Sem prazo", kind: "neutral" };
  const hours = (date.getTime() - Date.now()) / 3_600_000;
  if (hours < 0) return { label: "Prazo encerrado", kind: "closed" };
  if (hours <= 24) return { label: "Abre em até 24h", kind: "critical" };
  if (hours <= 72) return { label: "Abre em até 3 dias", kind: "warning" };
  return { label: "Prazo regular", kind: "ok" };
}

function priorityLabel(priority: number) {
  return priority === 1 ? "Alta prioridade" : priority === 2 ? "Prioridade média" : "Baixa prioridade";
}

function shortText(value: string, maximum = 115) {
  const text = value.trim();
  return text.length <= maximum ? text : `${text.slice(0, maximum).trim()}...`;
}

function normalize(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function filterDate(value: string) {
  const date = parseDate(value);
  if (!date) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function businessPositionClass(position: number | null) {
  if (position === 1) return " position-first";
  if (position === 2) return " position-second";
  if (position === 3) return " position-third";
  return "";
}

interface BusinessCardProps {
  business: Business;
  onOpen: (id: string, tab?: DetailTab) => void;
  onRename: (business: Business, title: string) => Promise<void>;
  onPositionChange: (business: Business, position: number | null) => Promise<void>;
  onArchive: (business: Business) => void;
  onRemove: (business: Business) => void;
}

function BusinessCard({
  business,
  onOpen,
  onRename,
  onArchive,
  onPositionChange,
  onRemove,
}: BusinessCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState(business.titulo);
  const [savingTitle, setSavingTitle] = useState(false);
  const deadline = urgency(business);

  const beginTitleEdit = () => {
    setTitleDraft(business.titulo);
    setMenuOpen(false);
    setEditingTitle(true);
  };

  const saveTitle = async () => {
    const title = titleDraft.trim();
    if (!title || title === business.titulo) {
      if (title) setEditingTitle(false);
      return;
    }
    setSavingTitle(true);
    try {
      await onRename(business, title);
      setEditingTitle(false);
    } catch {
      // A mensagem de erro é exibida pelo bloco e o editor permanece aberto.
    } finally {
      setSavingTitle(false);
    }
  };
  const editPosition = async () => {
    setMenuOpen(false);
    const answer = window.prompt(
      "Informe a posição do item. Deixe em branco para remover:",
      business.position_number ? String(business.position_number) : "",
    );
    if (answer === null) return;
    const value = answer.trim();
    let position: number | null = null;
    if (value) {
      if (!/^\d+$/.test(value) || Number(value) < 1) {
        window.alert("A posição deve ser um número inteiro maior que zero.");
        return;
      }
      position = Number(value);
    }
    try {
      await onPositionChange(business, position);
    } catch {
      // A mensagem de erro é exibida pelo bloco.
    }
  };


  return (
    <article
      className={`business-card priority-${business.prioridade}${businessPositionClass(business.position_number)}`}
      draggable={business.pode_mover && !editingTitle}
      onDragStart={(event) => {
        event.dataTransfer.setData("text/business-id", business.id);
        event.dataTransfer.effectAllowed = "move";
      }}
      onClick={() => onOpen(business.id)}
    >
      <div className="business-card-topline">
        <span className="source-label">{business.plataforma || "PNCP"}</span>
        <span className={`urgency-label is-${deadline.kind}`}>{deadline.label}</span>
      </div>
      <div className="business-card-reference">
        <strong>{business.modalidade || "Modalidade não informada"}</strong>
        <span>{business.numero_compra || `PNCP ${business.ano}/${business.sequencial}`}</span>
      </div>
      {editingTitle ? (
        <div
          className="business-card-title-editor"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => {
            if (event.key === "Escape") setEditingTitle(false);
            if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) void saveTitle();
          }}
        >
          <textarea
            autoFocus
            rows={3}
            value={titleDraft}
            aria-label="Título do negócio"
            onChange={(event) => setTitleDraft(event.target.value)}
          />
          <div>
            <button
              type="button"
              disabled={savingTitle || !titleDraft.trim()}
              onClick={() => void saveTitle()}
            >
              <Check size={14} /> {savingTitle ? "Salvando..." : "Salvar"}
            </button>
            <button type="button" disabled={savingTitle} onClick={() => setEditingTitle(false)}>
              <X size={14} /> Cancelar
            </button>
          </div>
        </div>
      ) : (
        <div className="business-card-title-row">
          <h3 title={business.titulo_oficial || business.titulo}>
            {shortText(business.titulo || "Objeto da contratação não informado")}
          </h3>
          <button
            className="business-title-edit-button"
            type="button"
            title="Editar título"
            aria-label={`Editar título de ${business.titulo}`}
            onClick={(event) => {
              event.stopPropagation();
              beginTitleEdit();
            }}
          >
            <Pencil size={13} />
          </button>
        </div>
      )}
      <div className="business-card-org" title={business.orgao}>
        <Building2 size={15} aria-hidden="true" />
        <span>{business.orgao || "Órgão não informado"}</span>
      </div>
      <div className="business-card-location">
        <MapPin size={14} aria-hidden="true" />
        <span>
          {[business.municipio, business.uf].filter(Boolean).join(" / ") || "Local não informado"}
        </span>
      </div>
      <div className="business-card-opening">
        <CalendarClock size={14} aria-hidden="true" />
        <span>{openingLabel(business.abertura)}</span>
      </div>
      <div className="business-tags" aria-label="Marcadores">
        <span>{business.modalidade || "Sem modalidade"}</span>
        <span>{priorityLabel(business.prioridade)}</span>
        {business.situacao && <span>{business.situacao}</span>}
        {business.total_itens > 0 && <span>{business.total_itens} item(ns)</span>}
        <button
          className="business-position-button"
          type="button"
          title="Definir posição"
          aria-label={`Posição atual: ${business.position_number ?? "não definida"}. Editar posição`}
          onClick={(event) => {
            event.stopPropagation();
            void editPosition();
          }}
        >
          Posição: <strong>{business.position_number ?? "definir"}</strong>
          <Pencil size={10} />
        </button>
      </div>
      <div className="business-card-footer">
        <button
          className="checklist-progress"
          type="button"
          title="Abrir checklist"
          onClick={(event) => {
            event.stopPropagation();
            onOpen(business.id, "tarefas");
          }}
        >
          <CheckSquare2 size={15} />
          {business.checklist_concluido}/{business.checklist_total}
        </button>
        <div className="business-card-actions">
          <button
            className="business-icon-button"
            type="button"
            title="Arquivar"
            aria-label="Arquivar negócio"
            onClick={(event) => {
              event.stopPropagation();
              onArchive(business);
            }}
          >
            <Archive size={15} />
          </button>
          <button
            className="business-icon-button"
            type="button"
            title="Remover"
            aria-label="Remover negócio"
            onClick={(event) => {
              event.stopPropagation();
              onRemove(business);
            }}
          >
            <Trash2 size={15} />
          </button>
          <button
            className="business-icon-button"
            type="button"
            title="Ver detalhes"
            aria-label="Ver detalhes do negócio"
            onClick={(event) => {
              event.stopPropagation();
              onOpen(business.id);
            }}
          >
            <Eye size={16} />
          </button>
          <button
            className="business-icon-button"
            type="button"
            title="Mais ações"
            aria-label="Mais ações do negócio"
            onClick={(event) => {
              event.stopPropagation();
              setMenuOpen((current) => !current);
            }}
          >
            <MoreHorizontal size={17} />
          </button>
        </div>
      </div>
      {menuOpen && (
        <div className="business-card-menu" onClick={(event) => event.stopPropagation()}>
          <button type="button" onClick={beginTitleEdit}>
            <Pencil size={14} /> Editar título
          </button>
          <button
            type="button"
            onClick={() => {
              window.open(business.link_pncp, "_blank", "noopener,noreferrer");
              setMenuOpen(false);
            }}
          >
            <ExternalLink size={14} /> Abrir no PNCP
          </button>
          <button
            type="button"
            onClick={() => {
              onOpen(business.id);
              setMenuOpen(false);
            }}
          >
            <Eye size={14} /> Ver detalhes
          </button>
        </div>
      )}
    </article>
  );
}

interface BusinessDetailModalProps {
  businessId: string;
  initialTab: DetailTab;
  onClose: () => void;
  onBusinessChange: (business: Business) => void;
  onMove: (business: Business, stage: BusinessStage) => Promise<void>;
  onArchive: (business: Business) => void;
  onRemove: (business: Business) => void;
}

function BusinessDetailModal({
  businessId,
  initialTab,
  onClose,
  onBusinessChange,
  onMove,
  onArchive,
  onRemove,
}: BusinessDetailModalProps) {
  const [detail, setDetail] = useState<BusinessDetail | null>(null);
  const [tab, setTab] = useState<DetailTab>(initialTab);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fullscreen, setFullscreen] = useState(false);
  const [newTask, setNewTask] = useState("");
  const [draft, setDraft] = useState({
    titulo: "",
    prioridade: 2 as 1 | 2 | 3,
    responsavel: "",
    prazo_interno: "",
    anotacoes: "",
    decisao_comercial: "",
  });
  const hasPendingChanges = detail !== null
    ? (
      draft.titulo !== detail.titulo
      || draft.prioridade !== detail.prioridade
      || draft.responsavel !== detail.responsavel
      || draft.prazo_interno !== detail.prazo_interno
      || draft.anotacoes !== detail.anotacoes
      || draft.decisao_comercial !== detail.decisao_comercial
    )
    : false;
  const requestClose = useCallback(() => {
    if (busy) return;
    if (hasPendingChanges && !window.confirm("Descartar as alterações não salvas?")) return;
    onClose();
  }, [busy, hasPendingChanges, onClose]);

  const loadDetail = useCallback(async () => {
    setError("");
    try {
      const loaded = await getBusiness(businessId);
      setDetail(loaded);
      setDraft({
        titulo: loaded.titulo,
        prioridade: loaded.prioridade,
        responsavel: loaded.responsavel,
        prazo_interno: loaded.prazo_interno,
        anotacoes: loaded.anotacoes,
        decisao_comercial: loaded.decisao_comercial,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar o negócio.");
    }
  }, [businessId]);

  useEffect(() => {
    void loadDetail();
  }, [loadDetail]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [requestClose]);

  const save = async () => {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      const updated = await updateBusiness(detail.id, {
        titulo_interno: draft.titulo,
        prioridade: draft.prioridade,
        responsavel: draft.responsavel,
        prazo_interno: draft.prazo_interno,
        anotacoes: draft.anotacoes,
        decisao_comercial: draft.decisao_comercial,
      });
      onBusinessChange(updated);
      await loadDetail();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível salvar.");
    } finally {
      setBusy(false);
    }
  };

  const toggleTask = async (taskId: string, checked: boolean) => {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      const updated = await updateBusinessTask(detail.id, taskId, checked);
      setDetail(updated);
      onBusinessChange(updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível atualizar a tarefa.");
    } finally {
      setBusy(false);
    }
  };

  const createTask = async () => {
    if (!detail || !newTask.trim()) return;
    setBusy(true);
    try {
      const updated = await addBusinessTask(detail.id, newTask.trim());
      setDetail(updated);
      onBusinessChange(updated);
      setNewTask("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível criar a tarefa.");
    } finally {
      setBusy(false);
    }
  };

  const share = async () => {
    const url = `${window.location.origin}${window.location.pathname}#negocio-${businessId}`;
    try {
      await navigator.clipboard.writeText(url);
    } catch {
      window.prompt("Link do negócio", url);
    }
  };

  return (
    <div
      className="business-modal-backdrop"
      onMouseDown={(event) => {
        if (event.currentTarget === event.target) requestClose();
      }}
    >
      <section
        className={`business-detail-modal${fullscreen ? " is-fullscreen" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label="Detalhes do negócio"
      >
        <header className="business-detail-header">
          <div>
            <span>Negócio #{businessId}</span>
            <strong>{detail?.numero_compra || "Carregando contratação"}</strong>
          </div>
          <div className="business-detail-top-actions">
            <button
              type="button"
              className={`business-icon-button${detail?.favorito ? " is-favorite" : ""}`}
              title={detail?.favorito ? "Remover dos favoritos" : "Adicionar aos favoritos"}
              aria-label="Alternar favorito"
              disabled={!detail || busy}
              onClick={async () => {
                if (!detail) return;
                try {
                  const updated = await updateBusiness(detail.id, {
                    favorito: !detail.favorito,
                  });
                  setDetail({ ...detail, ...updated });
                  onBusinessChange(updated);
                } catch (reason) {
                  setError(reason instanceof Error ? reason.message : "Não foi possível atualizar o favorito.");
                }
              }}
            >
              <Star size={18} fill={detail?.favorito ? "currentColor" : "none"} />
            </button>
            <button
              type="button"
              className="business-icon-button"
              title="Copiar link"
              aria-label="Copiar link"
              onClick={share}
            >
              <Link2 size={18} />
            </button>
            <button
              type="button"
              className="business-icon-button"
              title={fullscreen ? "Sair da tela cheia" : "Tela cheia"}
              aria-label="Alternar tela cheia"
              onClick={() => setFullscreen((current) => !current)}
            >
              {fullscreen ? <Fullscreen size={18} /> : <Maximize2 size={18} />}
            </button>
            <button
              type="button"
              className="business-icon-button"
              title="Fechar"
              aria-label="Fechar detalhes"
              disabled={busy}
              onClick={requestClose}
            >
              <X size={20} />
            </button>
          </div>
        </header>

        {!detail && !error && (
          <div className="business-detail-loading">
            <LoaderCircle className="spin" size={22} />
            Carregando dados do PNCP...
          </div>
        )}
        {error && <div className="business-inline-error">{error}</div>}

        {detail && (
          <>
            <div className="business-identification-strip">
              <span><strong>Fonte</strong>{detail.plataforma}</span>
              <span><strong>Modalidade</strong>{detail.modalidade || "Não informada"}</span>
              <span><strong>Compra</strong>{detail.numero_compra || "Não informada"}</span>
              <span><strong>Processo</strong>{detail.processo || "Não informado"}</span>
              <span><strong>Comprador</strong>{detail.orgao || "Não informado"}</span>
            </div>
            <div className="business-detail-title">
              <span>Título oficial</span>
              <h2>{detail.titulo_oficial || "Objeto não informado"}</h2>
            </div>

            <div className="business-stage-selector" aria-label="Etapa do negócio">
              {STAGES.map((stage) => (
                <button
                  key={stage.id}
                  type="button"
                  className={detail.etapa === stage.id ? "is-current" : ""}
                  disabled={busy}
                  onClick={async () => {
                    if (detail.etapa === stage.id) return;
                    setBusy(true);
                    try {
                      await onMove(detail, stage.id);
                      await loadDetail();
                    } catch (reason) {
                      setError(reason instanceof Error ? reason.message : "Não foi possível alterar a etapa.");
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  <span>{STAGE_INDEX[stage.id] + 1}</span>
                  {stage.label}
                </button>
              ))}
            </div>

            <div className="business-operational-actions">
              <a
                className="business-operation"
                href={detail.link_pncp}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={19} />
                <span><strong>Acessar</strong><small>Fonte oficial</small></span>
              </a>
              <button type="button" className="business-operation" onClick={() => setTab("tarefas")}>
                <ClipboardList size={19} />
                <span><strong>Tarefas</strong><small>{detail.checklist_concluido}/{detail.checklist_total}</small></span>
              </button>
              <button type="button" className="business-operation" onClick={() => setTab("documentos")}>
                <FileText size={19} />
                <span><strong>Documentação</strong><small>Arquivos internos</small></span>
              </button>
              <button type="button" className="business-operation" onClick={() => setTab("arquivos")}>
                <FileArchive size={19} />
                <span><strong>Arquivos do edital</strong><small>{detail.arquivos.length} oficial(is)</small></span>
              </button>
            </div>

            <nav className="business-detail-tabs" aria-label="Conteúdo do negócio">
              {([
                ["dados", "Dados"],
                ["itens", `Itens (${detail.itens.length})`],
                ["tarefas", "Checklist"],
                ["documentos", "Documentação"],
                ["arquivos", "Edital"],
                ["historico", "Histórico"],
              ] as Array<[DetailTab, string]>).map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={tab === id ? "is-active" : ""}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="business-detail-content">
              {tab === "dados" && (
                <div className="business-detail-grid">
                  <label className="business-field is-wide">
                    Título interno
                    <input
                      value={draft.titulo}
                      onChange={(event) => setDraft({ ...draft, titulo: event.target.value })}
                    />
                    <small>O título oficial acima permanece inalterado.</small>
                  </label>
                  <label className="business-field">
                    Prioridade
                    <select
                      value={draft.prioridade}
                      onChange={(event) => setDraft({
                        ...draft,
                        prioridade: Number(event.target.value) as 1 | 2 | 3,
                      })}
                    >
                      <option value="1">Alta</option>
                      <option value="2">Média</option>
                      <option value="3">Baixa</option>
                    </select>
                  </label>
                  <label className="business-field">
                    Responsável
                    <input
                      value={draft.responsavel}
                      onChange={(event) => setDraft({ ...draft, responsavel: event.target.value })}
                      placeholder="Nome do responsável"
                    />
                  </label>
                  <label className="business-field">
                    Prazo interno
                    <input
                      type="datetime-local"
                      value={draft.prazo_interno}
                      onChange={(event) => setDraft({ ...draft, prazo_interno: event.target.value })}
                    />
                  </label>
                  <div className="business-readonly-field">
                    <strong>Local</strong>
                    <span>{[detail.municipio, detail.uf].filter(Boolean).join(" / ") || "Não informado"}</span>
                  </div>
                  <div className="business-readonly-field">
                    <strong>Abertura oficial</strong>
                    <span>{formatDateTime(detail.abertura)}</span>
                  </div>
                  <label className="business-field is-wide">
                    Anotações
                    <textarea
                      value={draft.anotacoes}
                      onChange={(event) => setDraft({ ...draft, anotacoes: event.target.value })}
                    />
                  </label>
                  <label className="business-field is-wide">
                    Decisão comercial
                    <textarea
                      value={draft.decisao_comercial}
                      onChange={(event) => setDraft({ ...draft, decisao_comercial: event.target.value })}
                    />
                  </label>
                  <div className="business-detail-save is-wide">
                    <button className="button button-primary" type="button" disabled={busy} onClick={save}>
                      {busy ? <LoaderCircle className="spin" size={17} /> : <Check size={17} />}
                      Salvar alterações
                    </button>
                  </div>
                </div>
              )}

              {tab === "tarefas" && (
                <div className="business-checklist">
                  <div className="business-checklist-heading">
                    <div>
                      <strong>Checklist operacional</strong>
                      <span>{detail.checklist_concluido} de {detail.checklist_total} concluídas</span>
                    </div>
                    <div className="business-progress-track">
                      <span
                        style={{
                          width: `${detail.checklist_total
                            ? (detail.checklist_concluido / detail.checklist_total) * 100
                            : 0}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className="business-task-list">
                    {detail.tarefas.map((task) => (
                      <label key={task.id} className={task.concluida ? "is-complete" : ""}>
                        <input
                          type="checkbox"
                          checked={task.concluida}
                          disabled={busy}
                          onChange={(event) => void toggleTask(task.id, event.target.checked)}
                        />
                        <span>{task.titulo}</span>
                      </label>
                    ))}
                  </div>
                  <div className="business-new-task">
                    <input
                      value={newTask}
                      placeholder="Nova tarefa"
                      onChange={(event) => setNewTask(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") void createTask();
                      }}
                    />
                    <button
                      className="button button-secondary"
                      type="button"
                      disabled={busy || !newTask.trim()}
                      onClick={() => void createTask()}
                    >
                      <Plus size={17} /> Adicionar
                    </button>
                  </div>
                </div>
              )}

              {tab === "itens" && (
                <div className="business-item-list">
                  {detail.itens.length ? detail.itens.map((item) => (
                    <article key={item.id}>
                      <header>
                        <span>Item {item.numero}{item.lote ? ` · Lote ${item.lote}` : ""}</span>
                        {item.situacao && <em>{item.situacao}</em>}
                      </header>
                      <p>{item.descricao}</p>
                      <dl>
                        <div><dt>Quantidade</dt><dd>{item.quantidade || "Não informada"}</dd></div>
                        <div><dt>Unidade</dt><dd>{item.unidade || "UND"}</dd></div>
                        <div><dt>Valor unitário</dt><dd>{formatCurrency(item.valor_unitario_estimado)}</dd></div>
                        <div><dt>Valor total</dt><dd>{formatCurrency(item.valor_total_estimado)}</dd></div>
                        <div><dt>Critério</dt><dd>{item.criterio_julgamento || "Não informado"}</dd></div>
                      </dl>
                    </article>
                  )) : (
                    <div className="business-empty-detail">
                      <PackageSearch size={26} />
                      <strong>Nenhum item vinculado</strong>
                      <span>Selecione os itens ao adicionar a oportunidade pelo Bloco 1.</span>
                    </div>
                  )}
                </div>
              )}

              {tab === "documentos" && (
                <div className="business-empty-detail">
                  <FileText size={26} />
                  <strong>Nenhum documento interno vinculado</strong>
                  <span>Os arquivos oficiais permanecem disponíveis na aba Edital.</span>
                </div>
              )}

              {tab === "arquivos" && (
                <div className="business-file-list">
                  {detail.arquivos.length ? detail.arquivos.map((file, index) => (
                    <a
                      key={`${file.url}-${index}`}
                      href={file.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <FileArchive size={18} />
                      <span>
                        <strong>{file.titulo}</strong>
                        <small>{file.tipo || "Arquivo oficial do PNCP"}</small>
                      </span>
                      {file.selecionado && <em>Usado na leitura</em>}
                      <ExternalLink size={15} />
                    </a>
                  )) : (
                    <div className="business-empty-detail">
                      <FileArchive size={26} />
                      <strong>Nenhum arquivo retornado</strong>
                      <span>A fonte oficial pode ser acessada pelo botão Acessar.</span>
                    </div>
                  )}
                </div>
              )}

              {tab === "historico" && (
                <div className="business-history">
                  {detail.historico.map((entry) => (
                    <div key={entry.id}>
                      <span />
                      <div>
                        <strong>{entry.evento}</strong>
                        {(entry.etapa_anterior || entry.etapa_nova) && (
                          <small>
                            {entry.etapa_anterior || "Início"} <ChevronRight size={12} /> {entry.etapa_nova}
                          </small>
                        )}
                        {entry.justificativa && <p>{entry.justificativa}</p>}
                        <time>{formatDateTime(entry.criado_em)}</time>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <footer className="business-detail-footer">
              <div>
                <button
                  className="button button-secondary button-small"
                  type="button"
                  onClick={() => onArchive(detail)}
                >
                  <Archive size={15} /> Arquivar
                </button>
                <button
                  className="button button-danger button-small"
                  type="button"
                  onClick={() => onRemove(detail)}
                >
                  <Trash2 size={15} /> Remover
                </button>
              </div>
              <span>Atualizado em {formatDateTime(detail.atualizado_em)}</span>
            </footer>
          </>
        )}
      </section>
    </div>
  );
}

interface BusinessBlockProps {
  responsibles: Responsible[];
  onOpenClassifications: () => void;
}

export function BusinessBlock({ responsibles, onOpenClassifications }: BusinessBlockProps) {
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [filters, setFilters] = useState<BusinessFilters>(EMPTY_FILTERS);
  const [sort, setSort] = useState("updated");
  const [view, setView] = useState<BusinessView>("kanban");
  const [selectedCompany, setSelectedCompany] = useState("");
  const [importOpen, setImportOpen] = useState(false);
  const [importLink, setImportLink] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [detailId, setDetailId] = useState("");
  const [detailTab, setDetailTab] = useState<DetailTab>("dados");

  const companies = useMemo(() => Array.from(new Set(
    [
      ...responsibles.map((item) => item.empresa),
      ...businesses.map((item) => item.empresa),
    ].filter(Boolean),
  )).sort((a, b) => a.localeCompare(b, "pt-BR")), [businesses, responsibles]);

  useEffect(() => {
    if (!selectedCompany && companies.length) setSelectedCompany(companies[0]);
  }, [companies, selectedCompany]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBusinesses(await listBusinesses());
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível carregar os negócios.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const refresh = () => void load();
    window.addEventListener("toth:business-updated", refresh);
    return () => window.removeEventListener("toth:business-updated", refresh);
  }, [load]);

  useEffect(() => {
    const match = window.location.hash.match(/^#negocio-(\d+)$/);
    if (match) setDetailId(match[1]);
  }, []);

  const modalities = useMemo(
    () => Array.from(new Set(businesses.map((item) => item.modalidade).filter(Boolean))).sort(),
    [businesses],
  );
  const platforms = useMemo(
    () => Array.from(new Set(businesses.map((item) => item.plataforma).filter(Boolean))).sort(),
    [businesses],
  );
  const statuses = useMemo(
    () => Array.from(new Set(businesses.map((item) => item.situacao).filter(Boolean))).sort(),
    [businesses],
  );

  const filtered = useMemo(() => {
    const keyword = normalize(filters.keyword);
    const tags = normalize(filters.tags);
    const rows = businesses.filter((business) => {
      if (selectedCompany && business.empresa !== selectedCompany) return false;
      if (filters.modalidade && business.modalidade !== filters.modalidade) return false;
      if (filters.plataforma && business.plataforma !== filters.plataforma) return false;
      if (filters.etapa && business.etapa !== filters.etapa) return false;
      if (filters.situacao && business.situacao !== filters.situacao) return false;
      const opening = filterDate(business.abertura);
      if (filters.aberturaInicial && (!opening || opening < filters.aberturaInicial)) return false;
      if (filters.aberturaFinal && (!opening || opening > filters.aberturaFinal)) return false;
      const haystack = normalize([
        business.titulo,
        business.titulo_oficial,
        business.orgao,
        business.numero_compra,
        business.processo,
        business.municipio,
        business.uf,
      ].join(" "));
      if (keyword && !haystack.includes(keyword)) return false;
      const tagValues = normalize([
        business.plataforma,
        business.modalidade,
        business.fonte_integracao,
        priorityLabel(business.prioridade),
        business.situacao,
      ].join(" "));
      return !tags || tagValues.includes(tags);
    });
    return rows.sort((a, b) => {
      if (sort === "oldest") return parseDate(a.criado_em)!.getTime() - parseDate(b.criado_em)!.getTime();
      if (sort === "opening-near") return (parseDate(a.abertura)?.getTime() || Infinity) - (parseDate(b.abertura)?.getTime() || Infinity);
      if (sort === "opening-far") return (parseDate(b.abertura)?.getTime() || -Infinity) - (parseDate(a.abertura)?.getTime() || -Infinity);
      if (sort === "priority") return a.prioridade - b.prioridade;
      if (sort === "newest") return parseDate(b.criado_em)!.getTime() - parseDate(a.criado_em)!.getTime();
      return (parseDate(b.atualizado_em)?.getTime() || 0) - (parseDate(a.atualizado_em)?.getTime() || 0);
    });
  }, [businesses, filters, selectedCompany, sort]);

  const appliedFilters = Object.entries(filters).filter(([, value]) => value);

  const replaceBusiness = (updated: Business) => {
    setBusinesses((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
  };

  const renameBusiness = async (business: Business, title: string) => {
    setError("");
    try {
      const updated = await updateBusiness(business.id, { titulo_interno: title });
      replaceBusiness(updated);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Não foi possível alterar o título.";
      setError(message);
      throw reason;
    }
  };

  const changeBusinessPosition = async (business: Business, position: number | null) => {
    setError("");
    try {
      const updated = await updateBusiness(business.id, { position_number: position });
      replaceBusiness(updated);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Não foi possível alterar a posição.";
      setError(message);
      throw reason;
    }
  };

  const changeStage = async (business: Business, stage: BusinessStage) => {
    if (business.etapa === stage) return;
    const sensitive = stage === "contrato" || STAGE_INDEX[stage] < STAGE_INDEX[business.etapa];
    let justification = "";
    if (sensitive) {
      justification = window.prompt("Informe a justificativa desta movimentação:")?.trim() || "";
      if (!justification) return;
    }
    const previous = business;
    replaceBusiness({ ...business, etapa: stage });
    try {
      replaceBusiness(await moveBusiness(business.id, stage, justification));
    } catch (reason) {
      replaceBusiness(previous);
      const message = reason instanceof Error ? reason.message : "Não foi possível mover o negócio.";
      setError(`${message} A etapa anterior foi restaurada.`);
      throw reason;
    }
  };

  const archiveBusiness = async (business: Business) => {
    if (!window.confirm(`Arquivar o negócio "${shortText(business.titulo, 60)}"?`)) return;
    try {
      await updateBusiness(business.id, { arquivado: true, justificativa: "Arquivado pelo usuário" });
      setBusinesses((current) => current.filter((item) => item.id !== business.id));
      if (detailId === business.id) setDetailId("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível arquivar.");
    }
  };

  const removeBusiness = async (business: Business) => {
    if (!window.confirm("Remover este negócio da visão ativa? O histórico será preservado.")) return;
    try {
      await updateBusiness(business.id, { removido: true, justificativa: "Removido pelo usuário" });
      setBusinesses((current) => current.filter((item) => item.id !== business.id));
      if (detailId === business.id) setDetailId("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível remover.");
    }
  };

  const submitImport = async () => {
    setImportBusy(true);
    setError("");
    try {
      const imported = await importBusiness(importLink, selectedCompany || companies[0] || "");
      setBusinesses((current) => {
        const exists = current.some((item) => item.id === imported.id);
        return exists
          ? current.map((item) => item.id === imported.id ? imported : item)
          : [imported, ...current];
      });
      setImportLink("");
      setImportOpen(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível adicionar a oportunidade.");
    } finally {
      setImportBusy(false);
    }
  };

  return (
    <section className="business-workspace">
      <div className="business-toolbar">
        <div className="business-toolbar-primary">
          <label className="business-company-select">
            Empresa
            <select value={selectedCompany} onChange={(event) => setSelectedCompany(event.target.value)}>
              {companies.length
                ? companies.map((company) => <option key={company}>{company}</option>)
                : <option value="">Empresa principal</option>}
            </select>
          </label>
          <button
            className={`button button-secondary${filtersOpen ? " is-active" : ""}`}
            type="button"
            onClick={() => setFiltersOpen((current) => !current)}
          >
            <Filter size={17} /> Filtros
            {appliedFilters.length > 0 && <span className="filter-count">{appliedFilters.length}</span>}
          </button>
          <label className="business-sort">
            <ArrowDownUp size={16} aria-hidden="true" />
            <select value={sort} aria-label="Ordenar negócios" onChange={(event) => setSort(event.target.value)}>
              <option value="updated">Última atualização</option>
              <option value="newest">Mais recentes</option>
              <option value="oldest">Mais antigos</option>
              <option value="opening-near">Abertura mais próxima</option>
              <option value="opening-far">Abertura mais distante</option>
              <option value="priority">Maior prioridade</option>
            </select>
          </label>
        </div>
        <div className="business-toolbar-actions">
          <div className="business-view-switcher" aria-label="Modo de visualização">
            <button
              type="button"
              className={view === "kanban" ? "is-active" : ""}
              title="Kanban"
              aria-label="Visualização Kanban"
              onClick={() => setView("kanban")}
            >
              <Grid3X3 size={17} />
            </button>
            <button
              type="button"
              className={view === "list" ? "is-active" : ""}
              title="Lista"
              aria-label="Visualização em lista"
              onClick={() => setView("list")}
            >
              <List size={17} />
            </button>
            <button
              type="button"
              className={view === "table" ? "is-active" : ""}
              title="Tabela compacta"
              aria-label="Visualização em tabela"
              onClick={() => setView("table")}
            >
              <Table2 size={17} />
            </button>
          </div>
          <button className="button button-primary" type="button" onClick={() => setImportOpen(true)}>
            <Plus size={17} /> Adicionar
          </button>
        </div>
      </div>

      {filtersOpen && (
        <div className="business-filter-panel">
          <label>
            Palavra-chave
            <div className="business-input-icon">
              <Search size={16} />
              <input
                value={filters.keyword}
                placeholder="Objeto, órgão, processo..."
                onChange={(event) => setFilters({ ...filters, keyword: event.target.value })}
              />
            </div>
          </label>
          <label>
            Modalidade
            <select
              value={filters.modalidade}
              onChange={(event) => setFilters({ ...filters, modalidade: event.target.value })}
            >
              <option value="">Todas</option>
              {modalities.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Plataforma
            <select
              value={filters.plataforma}
              onChange={(event) => setFilters({ ...filters, plataforma: event.target.value })}
            >
              <option value="">Todas</option>
              {platforms.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Abertura inicial
            <input
              type="date"
              value={filters.aberturaInicial}
              onChange={(event) => setFilters({ ...filters, aberturaInicial: event.target.value })}
            />
          </label>
          <label>
            Abertura final
            <input
              type="date"
              value={filters.aberturaFinal}
              onChange={(event) => setFilters({ ...filters, aberturaFinal: event.target.value })}
            />
          </label>
          <label>
            Etapa
            <select value={filters.etapa} onChange={(event) => setFilters({ ...filters, etapa: event.target.value })}>
              <option value="">Todas</option>
              {STAGES.map((stage) => <option key={stage.id} value={stage.id}>{stage.label}</option>)}
            </select>
          </label>
          <label>
            Status
            <select
              value={filters.situacao}
              onChange={(event) => setFilters({ ...filters, situacao: event.target.value })}
            >
              <option value="">Todos</option>
              {statuses.map((value) => <option key={value}>{value}</option>)}
            </select>
          </label>
          <label>
            Marcadores
            <input
              value={filters.tags}
              placeholder="Prioridade, origem..."
              onChange={(event) => setFilters({ ...filters, tags: event.target.value })}
            />
          </label>
        </div>
      )}

      {appliedFilters.length > 0 && (
        <div className="business-applied-filters">
          <span>Filtros aplicados</span>
          {appliedFilters.map(([key, value]) => (
            <button
              key={key}
              type="button"
              onClick={() => setFilters({ ...filters, [key]: "" })}
            >
              {value}<X size={13} />
            </button>
          ))}
          <button type="button" className="clear-all" onClick={() => setFilters(EMPTY_FILTERS)}>
            Limpar todos
          </button>
        </div>
      )}

      {error && (
        <div className="business-inline-error">
          <span>{error}</span>
          <button type="button" aria-label="Fechar mensagem" onClick={() => setError("")}><X size={16} /></button>
        </div>
      )}

      {loading ? (
        <div className="business-loading">
          <LoaderCircle className="spin" size={22} />
          Carregando negócios...
        </div>
      ) : view === "kanban" ? (
        <div className="business-kanban">
          {STAGES.map((stage) => {
            const stageBusinesses = filtered.filter((business) => business.etapa === stage.id);
            return (
              <section
                key={stage.id}
                className={`business-column stage-${stage.id}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  event.dataTransfer.dropEffect = "move";
                }}
                onDrop={(event) => {
                  event.preventDefault();
                  const id = event.dataTransfer.getData("text/business-id");
                  const business = businesses.find((item) => item.id === id);
                  if (business) void changeStage(business, stage.id);
                }}
              >
                <header>
                  <div>
                    <h2>{stage.label}</h2>
                    <p>{stage.description}</p>
                  </div>
                  <span>{stageBusinesses.length}</span>
                  {stage.id === "classificacao" ? (
                    <button
                      className="business-classification-button"
                      type="button"
                      onClick={onOpenClassifications}
                      aria-label="Visualizar classificações por portal"
                    >
                      <Eye size={15} /> Visualizar classificações
                    </button>
                  ) : null}
                </header>
                <div className="business-column-scroll">
                  {stageBusinesses.length ? stageBusinesses.map((business) => (
                    <BusinessCard
                      key={business.id}
                      business={business}
                      onRename={renameBusiness}
                      onOpen={(id, tab = "dados") => {
                        setDetailTab(tab);
                        setDetailId(id);
                      }}
                      onPositionChange={changeBusinessPosition}
                      onArchive={(item) => void archiveBusiness(item)}
                      onRemove={(item) => void removeBusiness(item)}
                    />
                  )) : (
                    <div className="business-column-empty">
                      <ClipboardList size={22} />
                      <span>Nenhum negócio nesta etapa</span>
                    </div>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      ) : view === "list" ? (
        <div className="business-list-view">
          {filtered.map((business) => (
            <button
              key={business.id}
              type="button"
              className="business-list-row"
              onClick={() => {
                setDetailTab("dados");
                setDetailId(business.id);
              }}
            >
              <span className={`business-list-priority priority-${business.prioridade}`} />
              <span>
                <strong>{business.titulo}</strong>
                <small>{business.orgao} · {[business.municipio, business.uf].filter(Boolean).join(" / ")}</small>
              </span>
              <em>{STAGES.find((stage) => stage.id === business.etapa)?.label}</em>
              <span>{openingLabel(business.abertura)}</span>
              <ChevronRight size={18} />
            </button>
          ))}
          {!filtered.length && <div className="business-empty-view">Nenhum negócio corresponde aos filtros.</div>}
        </div>
      ) : (
        <div className="business-table-wrap">
          <table className="business-table">
            <thead>
              <tr>
                <th>Compra</th>
                <th>Objeto</th>
                <th>Órgão</th>
                <th>Etapa</th>
                <th>Abertura</th>
                <th>Checklist</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((business) => (
                <tr
                  key={business.id}
                  tabIndex={0}
                  onClick={() => {
                    setDetailTab("dados");
                    setDetailId(business.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") setDetailId(business.id);
                  }}
                >
                  <td>{business.numero_compra || `${business.ano}/${business.sequencial}`}</td>
                  <td title={business.titulo_oficial}>{shortText(business.titulo, 90)}</td>
                  <td>{business.orgao}</td>
                  <td>{STAGES.find((stage) => stage.id === business.etapa)?.label}</td>
                  <td>{formatDateTime(business.abertura)}</td>
                  <td>{business.checklist_concluido}/{business.checklist_total}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && <div className="business-empty-view">Nenhum negócio corresponde aos filtros.</div>}
        </div>
      )}

      <Modal
        open={importOpen}
        title="Adicionar oportunidade"
        busy={importBusy}
        onClose={() => setImportOpen(false)}
      >
        <div className="business-import-form">
          <p>Informe o link público da contratação. Os dados serão consultados diretamente na API oficial do PNCP.</p>
          <label>
            Empresa
            <select value={selectedCompany} onChange={(event) => setSelectedCompany(event.target.value)}>
              {companies.map((company) => <option key={company}>{company}</option>)}
            </select>
          </label>
          <label>
            Link do edital no PNCP
            <input
              value={importLink}
              autoFocus
              placeholder="https://pncp.gov.br/app/editais/CNPJ/ANO/SEQUENCIAL"
              onChange={(event) => setImportLink(event.target.value)}
            />
          </label>
          <div className="business-import-actions">
            <button className="button button-secondary" type="button" disabled={importBusy} onClick={() => setImportOpen(false)}>
              Cancelar
            </button>
            <button className="button button-primary" type="button" disabled={importBusy || !importLink.trim()} onClick={() => void submitImport()}>
              {importBusy ? <LoaderCircle className="spin" size={17} /> : <Plus size={17} />}
              Adicionar ao Kanban
            </button>
          </div>
        </div>
      </Modal>

      {detailId && (
        <BusinessDetailModal
          businessId={detailId}
          initialTab={detailTab}
          onClose={() => {
            setDetailId("");
            if (window.location.hash.startsWith("#negocio-")) history.replaceState(null, "", window.location.pathname);
          }}
          onBusinessChange={replaceBusiness}
          onMove={changeStage}
          onArchive={(item) => void archiveBusiness(item)}
          onRemove={(item) => void removeBusiness(item)}
        />
      )}
    </section>
  );
}
