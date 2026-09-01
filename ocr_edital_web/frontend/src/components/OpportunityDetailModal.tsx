import { useEffect, useMemo, useState } from "react";
import {
  BookOpen,
  BriefcaseBusiness,
  ChevronDown,
  ExternalLink,
  FileText,
  MessageSquareText,
  Search,
  Send,
} from "lucide-react";
import {
  askOpportunityDocument,
  convertOpportunityToBusiness,
  getOpportunityDetail,
  importBusiness,
  requestOpportunityEnrichment,
} from "../api";
import type {
  Bid,
  OpportunityAnswer,
  OpportunityDetail,
  OpportunityItemSelection,
  UiMessage,
} from "../types";
import { normalizePncpUrl, parseLocalDate } from "../utils";
import { opportunityItemKey, selectedOpportunityItems } from "../opportunitySelection";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

interface OpportunityDetailModalProps {
  bid: Bid | null;
  onClose: () => void;
  onGenerateProposal: (selection: OpportunityItemSelection) => void;
  onGenerateCatalog: (selection: OpportunityItemSelection) => void;
}

const DETAIL_REFRESH_INTERVAL_MS = 1_000;
const DETAIL_REFRESH_MAX_ATTEMPTS = 12;

function formatCurrency(value: number | string | null) {
  if (value === null || value === "") return "Não informado";
  const number = Number(String(value).replace(",", "."));
  if (!Number.isFinite(number)) return String(value);
  return number.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDateTime(value: string) {
  if (!value) return "Não informado";
  const date = parseLocalDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function OpportunityDetailModal({
  bid,
  onClose,
  onGenerateProposal,
  onGenerateCatalog,
}: OpportunityDetailModalProps) {
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const [selectionDrafts, setSelectionDrafts] = useState<Record<string, string[]>>({});
  const [activePanel, setActivePanel] = useState<"files" | "chat" | null>(null);
  const [itemSearch, setItemSearch] = useState("");
  const [openItems, setOpenItems] = useState<Set<string>>(new Set());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<OpportunityAnswer | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    if (!bid) return;
    let cancelled = false;
    let enrichmentRequested = false;
    let refreshTimer: number | undefined;
    setDetail(null);
    setMessage(null);
    setLoading(true);
    setAdded(false);
    setActivePanel(null);
    setItemSearch("");
    setOpenItems(new Set());
    setQuestion("");
    setAnswer(null);
    const loadDetail = async (attempt: number) => {
      try {
        const payload = await getOpportunityDetail(bid);
        if (cancelled) return;
        setDetail(payload);
        if (attempt === 0) setLoading(false);
        if (payload.enriquecimento_disponivel && !enrichmentRequested && bid.id) {
          enrichmentRequested = true;
          await requestOpportunityEnrichment(bid.id);
          if (cancelled) return;
          refreshTimer = window.setTimeout(
            () => void loadDetail(attempt + 1),
            DETAIL_REFRESH_INTERVAL_MS,
          );
        } else if (payload.enriquecimento_pendente && attempt < DETAIL_REFRESH_MAX_ATTEMPTS) {
          refreshTimer = window.setTimeout(
            () => void loadDetail(attempt + 1),
            DETAIL_REFRESH_INTERVAL_MS,
          );
        }
      } catch (error) {
        if (!cancelled && attempt === 0) {
          setMessage({
            kind: "error",
            text: error instanceof Error ? error.message : "Não foi possível carregar a oportunidade.",
          });
        }
      } finally {
        if (!cancelled && attempt === 0) setLoading(false);
      }
    };
    void loadDetail(0);
    return () => {
      cancelled = true;
      if (refreshTimer !== undefined) window.clearTimeout(refreshTimer);
    };
  }, [bid]);

  const filteredItems = useMemo(() => {
    if (!detail) return [];
    const term = itemSearch.trim().toLocaleLowerCase("pt-BR");
    if (!term) return detail.itens;
    return detail.itens.filter((item) =>
      [item.numero, item.lote, item.descricao, item.tipo]
        .join(" ")
        .toLocaleLowerCase("pt-BR")
        .includes(term),
    );
  }, [detail, itemSearch]);

  const selectionId = normalizePncpUrl(bid?.link || "") || bid?.link || "";
  const selectedKeys = new Set(selectionDrafts[selectionId] || []);
  const selectedItems = selectedOpportunityItems(detail?.itens || [], selectedKeys);

  const updateSelection = (update: (current: Set<string>) => Set<string>) => {
    if (adding) return;
    setSelectionDrafts((current) => ({
      ...current,
      [selectionId]: [...update(new Set(current[selectionId] || []))],
    }));
    setAdded(false);
    setMessage(null);
  };

  const useSelection = (onUse: (selection: OpportunityItemSelection) => void) => {
    if (!detail || !selectedItems.length || adding) return;
    onUse({ pncpLink: detail.oportunidade.link_pncp, items: selectedItems.map((item) => ({ ...item })) });
    onClose();
  };

  const addToBusiness = async () => {
    if (!bid || !detail || !selectedItems.length || adding) return;
    setAdding(true);
    setMessage(null);
    try {
      if (bid.id) {
        await convertOpportunityToBusiness(bid.id, selectedItems);
      } else {
        await importBusiness(bid.link, "", selectedItems, detail.oportunidade);
      }
      setAdded(true);
      setMessage({
        kind: "success",
        text: `${selectedItems.length} item(ns) adicionado(s) aos seus negócios.`,
      });
      window.dispatchEvent(new Event("toth:business-updated"));
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível adicionar a oportunidade.",
      });
    } finally {
      setAdding(false);
    }
  };

  const askDocument = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!bid || !question.trim()) return;
    setAsking(true);
    setAnswer(null);
    setMessage(null);
    try {
      setAnswer(await askOpportunityDocument(bid.link, question.trim()));
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível consultar o edital.",
      });
    } finally {
      setAsking(false);
    }
  };

  const opportunity = detail?.oportunidade;
  const title = opportunity
    ? `${opportunity.modalidade || "Contratação"} ${opportunity.numero_compra}`.trim()
    : "Detalhamento da oportunidade";

  return (
    <Modal
      open={Boolean(bid)}
      title={title}
      busy={adding || asking}
      onClose={onClose}
      wide
      className="opportunity-modal"
    >
      {loading ? <div className="opportunity-loading">Carregando detalhamento da oportunidade...</div> : null}
      <StatusMessage message={message} />
      {opportunity && detail ? (
        <div className="opportunity-detail">
          <header className="opportunity-summary">
            <div className="opportunity-source-line">
              <span>Portal de origem</span>
              <strong>{opportunity.portal_origem}</strong>
              {opportunity.situacao ? <span className="opportunity-status">{opportunity.situacao}</span> : null}
            </div>
            <h3>{opportunity.modalidade} {opportunity.numero_compra}</h3>
            <p className="opportunity-buyer">
              {opportunity.codigo_unidade
                ? `${opportunity.portal_origem === "Comprasnet" ? "UASG" : "Unidade"} ${opportunity.codigo_unidade} · `
                : ""}
              {opportunity.unidade || opportunity.orgao}
            </p>
            <p className="opportunity-object">{opportunity.objeto}</p>
            <div className="opportunity-tags" aria-label="Categorias da oportunidade">
              {opportunity.categorias.map((category) => <span key={category}>{category}</span>)}
            </div>
          </header>

          <dl className="opportunity-metrics">
            <div>
              <dt>Valor total estimado</dt>
              <dd>{formatCurrency(opportunity.valor_total_estimado)}</dd>
            </div>
            <div className="is-deadline">
              <dt>Data e horário de abertura</dt>
              <dd>{formatDateTime(opportunity.abertura)}</dd>
            </div>
            <div>
              <dt>Modo de disputa</dt>
              <dd>{opportunity.modo_disputa || "Não informado"}</dd>
            </div>
          </dl>

          <div className="opportunity-actions" aria-label="Ações da oportunidade">
            <button
              className="button button-secondary"
              type="button"
              onClick={() => window.open(opportunity.link_pncp, "_blank", "noopener,noreferrer")}
            >
              <ExternalLink size={17} />
              Acessar
            </button>
            <button
              className={`button button-secondary${activePanel === "files" ? " is-active" : ""}`}
              type="button"
              onClick={() => setActivePanel((current) => current === "files" ? null : "files")}
            >
              <FileText size={17} />
              Arquivos do edital
            </button>
            <button
              className={`button button-secondary${activePanel === "chat" ? " is-active" : ""}`}
              type="button"
              onClick={() => setActivePanel((current) => current === "chat" ? null : "chat")}
            >
              <MessageSquareText size={17} />
              Converse com o edital
            </button>
          </div>

          {activePanel === "files" ? (
            <section className="opportunity-panel" aria-labelledby="opportunity-files-heading">
              <div className="opportunity-panel-heading">
                <h4 id="opportunity-files-heading">Arquivos oficiais</h4>
                <span>{detail.fontes.arquivos}</span>
              </div>
              {detail.arquivos.length ? (
                <div className="opportunity-file-list">
                  {detail.arquivos.map((file, index) => (
                    <a key={`${file.url}-${index}`} href={file.url} target="_blank" rel="noreferrer">
                      <FileText size={17} />
                      <span><strong>{file.titulo}</strong><small>{file.tipo}</small></span>
                      <ExternalLink size={15} />
                    </a>
                  ))}
                </div>
              ) : <p className="opportunity-panel-empty">Nenhum arquivo foi retornado pelo PNCP.</p>}
            </section>
          ) : null}

          {activePanel === "chat" ? (
            <section className="opportunity-panel" aria-labelledby="opportunity-chat-heading">
              <div className="opportunity-panel-heading">
                <h4 id="opportunity-chat-heading">Converse com o edital</h4>
                <span>Respostas fundamentadas no Termo de Referência ou Edital oficial</span>
              </div>
              <form className="opportunity-chat-form" onSubmit={askDocument}>
                <input
                  value={question}
                  maxLength={500}
                  placeholder="Pergunte sobre prazo, entrega, especificações ou condições"
                  aria-label="Pergunta sobre o edital"
                  onChange={(event) => setQuestion(event.target.value)}
                />
                <button className="button button-primary" type="submit" disabled={asking || !question.trim()}>
                  <Send size={17} />
                  {asking ? "Consultando arquivo..." : "Perguntar"}
                </button>
              </form>
              {answer ? (
                <div className="opportunity-answer">
                  <p>{answer.resposta}</p>
                  {answer.trechos.map((excerpt, index) => <blockquote key={index}>{excerpt}</blockquote>)}
                  <small>Fonte: {answer.tipo_documento} · {answer.documento}</small>
                </div>
              ) : null}
            </section>
          ) : null}

          <section
            className="opportunity-items"
            aria-labelledby="opportunity-items-heading"
          >
            <div className="opportunity-items-heading">
              <div>
                <h4 id="opportunity-items-heading">Itens da contratação</h4>
                <span>{detail.itens.length.toLocaleString("pt-BR")} item(ns) · {detail.fontes.itens}</span>
              </div>
              <label className="opportunity-item-search">
                <Search size={17} />
                <input
                  value={itemSearch}
                  placeholder="Pesquisar itens"
                  aria-label="Pesquisar itens"
                  onChange={(event) => setItemSearch(event.target.value)}
                />
              </label>
            </div>
            {detail.aviso_enriquecimento ? (
              <StatusMessage
                compact
                message={{ kind: "warning", text: detail.aviso_enriquecimento }}
              />
            ) : null}
            {detail.verificacao_itens?.api_error ? (
              <StatusMessage
                compact
                message={{
                  kind: "warning",
                  text: "A consulta estruturada de itens não respondeu. Os itens exibidos foram recuperados do documento oficial.",
                }}
              />
            ) : null}
            {detail.verificacao_itens?.has_divergence && !detail.verificacao_itens.file_error ? (
              <StatusMessage
                compact
                message={{
                  kind: "warning",
                  text: `Conferência automática: documento oficial com ${detail.verificacao_itens.file_count} item(ns) e API do PNCP com ${detail.verificacao_itens.pncp_count}. A relação do documento está sendo priorizada.`,
                }}
              />
            ) : null}
            {detail.verificacao_itens?.file_error ? (
              <StatusMessage
                compact
                message={{
                  kind: "warning",
                  text: "Não foi possível conferir o documento oficial. Os itens exibidos vieram da API do PNCP.",
                }}
              />
            ) : null}
            {detail.itens.length > 0 ? (
              <div className="opportunity-selection-toolbar">
                <strong aria-live="polite">{selectedItems.length} de {detail.itens.length} item(ns) selecionado(s)</strong>
                <div>
                  <button
                    type="button"
                    disabled={adding || !filteredItems.length}
                    onClick={() => updateSelection((current) => {
                      const next = new Set(current);
                      filteredItems.forEach((item) => next.add(opportunityItemKey(item)));
                      return next;
                    })}
                  >
                    Selecionar exibidos
                  </button>
                  <button type="button" disabled={adding || !selectedItems.length} onClick={() => updateSelection(() => new Set())}>
                    Limpar seleção
                  </button>
                </div>
              </div>
            ) : null}
            <div className="opportunity-actions" role="group" aria-label="Ações dos itens selecionados">
              <button
                className="button button-secondary" type="button"
                disabled={adding || !selectedItems.length}
                onClick={() => useSelection(onGenerateProposal)}
              >
                <FileText size={17} /> Gerar proposta
              </button>
              <button
                className="button button-primary opportunity-business-action" type="button"
                disabled={adding || added || !selectedItems.length}
                onClick={() => void addToBusiness()}
              >
                <BriefcaseBusiness size={17} />
                {added ? "Adicionada aos negócios" : adding ? "Adicionando..." : "Adicionar aos meus negócios"}
              </button>
              <button
                className="button button-secondary" type="button"
                disabled={adding || !selectedItems.length}
                onClick={() => useSelection(onGenerateCatalog)}
              >
                <BookOpen size={17} /> Gerar catálogo
              </button>
            </div>
            <div className="opportunity-item-list">
              {filteredItems.map((item) => {
                const key = opportunityItemKey(item);
                const isOpen = openItems.has(key);
                const isSelected = selectedKeys.has(key);
                return (
                  <article
                    className={`opportunity-item is-selecting${isOpen ? " is-open" : ""}${isSelected ? " is-selected" : ""}`}
                    key={key}
                  >
                      <label className="opportunity-item-selector" aria-label={`Selecionar item ${item.numero}${item.lote ? ` do lote ${item.lote}` : ""}`}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={adding}
                          onChange={(event) => updateSelection((current) => {
                            const next = new Set(current);
                            if (event.target.checked) next.add(key);
                            else next.delete(key);
                            return next;
                          })}
                        />
                      </label>
                    <button
                      type="button"
                      aria-expanded={isOpen}
                      onClick={() => setOpenItems((current) => {
                        const next = new Set(current);
                        if (next.has(key)) next.delete(key);
                        else next.add(key);
                        return next;
                      })}
                    >
                      <span>Item {item.numero}{item.lote ? ` · Lote ${item.lote}` : ""}</span>
                      <strong>{item.descricao || "Descrição não informada"}</strong>
                      <ChevronDown size={18} />
                    </button>
                    {isOpen ? (
                      <div className="opportunity-item-details">
                        <p>{item.descricao}</p>
                        <dl>
                          <div><dt>Quantidade</dt><dd>{item.quantidade || "Não informada"}</dd></div>
                          <div><dt>Unidade</dt><dd>{item.unidade || "UND"}</dd></div>
                          <div><dt>Valor unitário estimado</dt><dd>{formatCurrency(item.valor_unitario_estimado)}</dd></div>
                          <div><dt>Valor total</dt><dd>{formatCurrency(item.valor_total_estimado)}</dd></div>
                          <div><dt>Critério</dt><dd>{item.criterio_julgamento || "Não informado"}</dd></div>
                          <div><dt>Situação</dt><dd>{item.situacao || "Não informada"}</dd></div>
                        </dl>
                      </div>
                    ) : null}
                  </article>
                );
              })}
              {!filteredItems.length ? (
                <p className="opportunity-panel-empty">
                  {detail.itens.length
                    ? "Nenhum item corresponde à pesquisa."
                    : "Nenhum item foi carregado para esta oportunidade."}
                </p>
              ) : null}
            </div>
          </section>

          <footer className="opportunity-footer">
            <span>Dados da oportunidade: {detail.fontes.oportunidade}</span>
          </footer>
        </div>
      ) : null}
    </Modal>
  );
}
