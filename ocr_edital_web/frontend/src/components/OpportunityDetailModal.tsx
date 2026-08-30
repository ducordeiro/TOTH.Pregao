import { useEffect, useMemo, useRef, useState } from "react";
import {
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
} from "../api";
import type {
  Bid,
  OpportunityAnswer,
  OpportunityDetail,
  UiMessage,
} from "../types";
import { parseLocalDate } from "../utils";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

interface OpportunityDetailModalProps {
  bid: Bid | null;
  onClose: () => void;
  onUseLink: (link: string) => void;
}

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
  onUseLink,
}: OpportunityDetailModalProps) {
  const itemsSectionRef = useRef<HTMLElement>(null);
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [added, setAdded] = useState(false);
  const [selectingForBusiness, setSelectingForBusiness] = useState(false);
  const [selectedBusinessItems, setSelectedBusinessItems] = useState<Set<string>>(new Set());
  const [activePanel, setActivePanel] = useState<"files" | "chat" | null>(null);
  const [itemSearch, setItemSearch] = useState("");
  const [openItems, setOpenItems] = useState<Set<string>>(new Set());
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<OpportunityAnswer | null>(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    if (!bid) return;
    let cancelled = false;
    setDetail(null);
    setMessage(null);
    setLoading(true);
    setAdded(false);
    setSelectingForBusiness(false);
    setSelectedBusinessItems(new Set());
    setActivePanel(null);
    setItemSearch("");
    setOpenItems(new Set());
    setQuestion("");
    setAnswer(null);
    getOpportunityDetail(bid)
      .then((payload) => {
        if (!cancelled) setDetail(payload);
      })
      .catch((error) => {
        if (!cancelled) {
          setMessage({
            kind: "error",
            text: error instanceof Error ? error.message : "Não foi possível carregar a oportunidade.",
          });
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
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

  const itemKey = (lote: string, numero: string) => `${lote}\u0000${numero}`;

  const addToBusiness = async () => {
    if (!bid || !detail || !selectedBusinessItems.size) return;
    const selectedItems = detail.itens.filter((item) =>
      selectedBusinessItems.has(itemKey(item.lote, item.numero)),
    );
    setAdding(true);
    setMessage(null);
    try {
      if (bid.id) {
        await convertOpportunityToBusiness(bid.id, selectedItems);
      } else {
        await importBusiness(bid.link, "", selectedItems, detail.oportunidade);
      }
      setAdded(true);
      setSelectingForBusiness(false);
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

  const startBusinessSelection = () => {
    setSelectingForBusiness(true);
    setSelectedBusinessItems(new Set());
    setMessage({ kind: "info", text: "Selecione os itens que deseja levar para o Bloco 4." });
    window.setTimeout(() => {
      itemsSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
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
      {loading ? <div className="opportunity-loading">Carregando dados oficiais do PNCP...</div> : null}
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
            <button
              className="button button-primary opportunity-business-action"
              type="button"
              disabled={
                adding
                || added
                || !detail.itens.length
                || (selectingForBusiness && !selectedBusinessItems.size)
              }
              onClick={() => {
                if (!selectingForBusiness) startBusinessSelection();
                else void addToBusiness();
              }}
            >
              <BriefcaseBusiness size={17} />
              {added
                ? "Adicionada aos negócios"
                : adding
                  ? "Adicionando..."
                  : selectingForBusiness
                    ? `Adicionar ${selectedBusinessItems.size} item(ns)`
                    : "Adicionar aos meus negócios"}
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
            ref={itemsSectionRef}
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
            {selectingForBusiness ? (
              <div className="opportunity-selection-toolbar">
                <strong>{selectedBusinessItems.size} de {detail.itens.length} item(ns) selecionado(s)</strong>
                <div>
                  <button
                    type="button"
                    onClick={() => setSelectedBusinessItems((current) => {
                      const next = new Set(current);
                      filteredItems.forEach((item) => next.add(itemKey(item.lote, item.numero)));
                      return next;
                    })}
                  >
                    Selecionar exibidos
                  </button>
                  <button type="button" onClick={() => setSelectedBusinessItems(new Set())}>
                    Limpar seleção
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectingForBusiness(false);
                      setSelectedBusinessItems(new Set());
                      setMessage(null);
                    }}
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            ) : null}
            <div className="opportunity-item-list">
              {filteredItems.map((item) => {
                const key = itemKey(item.lote, item.numero);
                const isOpen = openItems.has(key);
                const isSelected = selectedBusinessItems.has(key);
                return (
                  <article
                    className={`opportunity-item${isOpen ? " is-open" : ""}${selectingForBusiness ? " is-selecting" : ""}${isSelected ? " is-selected" : ""}`}
                    key={key}
                  >
                    {selectingForBusiness ? (
                      <label className="opportunity-item-selector" aria-label={`Selecionar item ${item.numero}`}>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(event) => setSelectedBusinessItems((current) => {
                            const next = new Set(current);
                            if (event.target.checked) next.add(key);
                            else next.delete(key);
                            return next;
                          })}
                        />
                      </label>
                    ) : null}
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
            <button
              className="button button-small button-secondary"
              type="button"
              onClick={() => {
                onClose();
                onUseLink(opportunity.link_pncp);
              }}
            >
              Usar no Bloco 2
            </button>
          </footer>
        </div>
      ) : null}
    </Modal>
  );
}
