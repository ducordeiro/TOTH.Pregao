import { useEffect, useMemo, useRef, useState } from "react";
import {
  Download,
  ExternalLink,
  FileOutput,
  Pencil,
  Upload,
  X,
} from "lucide-react";
import {
  generateProposal,
  getDocxStructure,
  identifyItems,
  processProposal,
} from "../api";
import type {
  DocumentNode,
  DocxStructureResponse,
  IdentifyResponse,
  MiniBoxTextAlign,
  OpportunityItemSelection,
  ProcessResponse,
  ProposalColumnWidths,
  ProposalItem,
  Responsible,
  Template,
  UiMessage,
} from "../types";
import {
  createDocumentBlockOrder,
  miniBoxOrderFromDocumentOrder,
} from "../docxOrder";
import { defaultProposalColumnWidths } from "../proposalPreviewLayout";
import { proposalItemsFromSelection, selectionForLink } from "../opportunitySelection";
import {
  calculateItemTotal,
  isValidPncpUrl,
  itemKey,
  normalizeMoney,
  normalizePncpUrl,
  parseMoneyToCents,
  sanitizeMoneyInput,
  validateTemplateFile,
} from "../utils";
import { StatusMessage } from "./StatusMessage";
import { DocxReorderBoard } from "./DocxReorderBoard";
import { ProposalLivePreview } from "./ProposalLivePreview";

interface ProposalBlockProps {
  pncpLink: string;
  onPncpLinkChange: (link: string) => void;
  itemSelection?: OpportunityItemSelection | null;
  templates: Template[];
  responsibles: Responsible[];
  selectedTemplateId: string;
  selectedResponsibleId: string;
  onSelectedTemplateChange: (id: string) => void;
  onSelectedResponsibleChange: (id: string) => void;
  onOpenTemplates: () => void;
  onOpenResponsibles: () => void;
}

interface ProcessedProposal {
  response: ProcessResponse;
  items: ProposalItem[];
}

function selectedKeysAsText(keys: Set<string>): string {
  return [...keys].sort((left, right) =>
    left.localeCompare(right, "pt-BR", { numeric: true }),
  ).join(", ");
}

function applyCommercialData(
  item: ProposalItem,
  brand: string,
  unitValue: string,
): ProposalItem {
  return {
    ...item,
    unidade: "UND",
    marca: brand || item.marca || "",
    valor_unitario: unitValue,
    valor_total: calculateItemTotal(item.quantidade, unitValue),
  };
}

export function ProposalBlock({
  pncpLink,
  onPncpLinkChange,
  itemSelection,
  templates,
  responsibles,
  selectedTemplateId,
  selectedResponsibleId,
  onSelectedTemplateChange,
  onSelectedResponsibleChange,
  onOpenTemplates,
  onOpenResponsibles,
}: ProposalBlockProps) {
  const customTemplateRef = useRef<HTMLInputElement>(null);
  const processVersionRef = useRef(0);
  const generationVersionRef = useRef(0);
  const [customTemplate, setCustomTemplate] = useState<File | null>(null);
  const [brand, setBrand] = useState("");
  const [identified, setIdentified] = useState<IdentifyResponse | null>(null);
  const [identifyMessage, setIdentifyMessage] = useState<UiMessage | null>({
    kind: "info",
    text: "Aguardando link PNCP.",
  });
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [unitValues, setUnitValues] = useState<Record<string, string>>({});
  const [processed, setProcessed] = useState<ProcessedProposal | null>(null);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [processing, setProcessing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [download, setDownload] = useState<{ url: string; filename: string } | null>(null);
  const [documentStructure, setDocumentStructure] = useState<DocxStructureResponse | null>(null);
  const [documentNodes, setDocumentNodes] = useState<DocumentNode[]>([]);
  const [documentBlockIds, setDocumentBlockIds] = useState<string[]>([]);
  const [miniBoxAlignments, setMiniBoxAlignments] = useState<Record<string, MiniBoxTextAlign>>({});
  const [proposalColumnWidths, setProposalColumnWidths] = useState<ProposalColumnWidths>(
    defaultProposalColumnWidths(false),
  );
  const [structureLoading, setStructureLoading] = useState(false);
  const [structureError, setStructureError] = useState("");

  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
  const selectedResponsible = responsibles.find(
    (responsible) => responsible.id === selectedResponsibleId,
  );
  const selectedTemplateVersion = selectedTemplate
    ? `${selectedTemplate.id}:${selectedTemplate.size}:${selectedTemplate.updated_at}`
    : "";
  const selectedTemplateVersionRef = useRef(selectedTemplateVersion);
  const showLot = Boolean(identified?.items.some((item) => String(item.lote || "").trim()));

  const resetProcessedTemplateState = () => {
    processVersionRef.current += 1;
    generationVersionRef.current += 1;
    setProcessing(false);
    setGenerating(false);
    setStructureLoading(false);
    setProcessed(null);
    setDownload(null);
    setDocumentStructure(null);
    setDocumentNodes([]);
    setDocumentBlockIds([]);
    setMiniBoxAlignments({});
    setProposalColumnWidths(defaultProposalColumnWidths(false));
    setStructureError("");
  };

  useEffect(() => {
    const previousVersion = selectedTemplateVersionRef.current;
    if (previousVersion === selectedTemplateVersion) return;
    selectedTemplateVersionRef.current = selectedTemplateVersion;
    setCustomTemplate(null);
    if (customTemplateRef.current) customTemplateRef.current.value = "";
    resetProcessedTemplateState();
    if (previousVersion) {
      setMessage({
        kind: "info",
        text: "Template cadastrado alterado. Processe novamente para aplicar o modelo selecionado.",
      });
    }
  }, [selectedTemplateVersion]);

  useEffect(() => {
    setIdentified(null);
    setSelectedKeys(new Set());
    setUnitValues({});
    resetProcessedTemplateState();
    setMessage(null);
    const link = pncpLink.trim();
    if (!link) {
      setIdentifyMessage({ kind: "info", text: "Aguardando link PNCP." });
      return;
    }
    const normalizedLink = normalizePncpUrl(link);
    if (!normalizedLink) {
      setIdentifyMessage({
        kind: "warning",
        text: "Informe uma URL pública válida do domínio pncp.gov.br.",
      });
      return;
    }

    const selection = selectionForLink(itemSelection, normalizedLink);
    if (selection) {
      const items = proposalItemsFromSelection(selection.items);
      setIdentified({ items });
      setSelectedKeys(new Set(items.map(itemKey)));
      setIdentifyMessage({
        kind: "success",
        text: `${items.length} item(ns) selecionado(s) no detalhamento.`,
      });
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIdentifyMessage({ kind: "info", text: "Consultando edital..." });
      try {
        const payload = await identifyItems(normalizedLink, controller.signal);
        if (controller.signal.aborted) return;
        setIdentified(payload);
        setSelectedKeys(new Set());
        setUnitValues(
          Object.fromEntries(
            (payload.items || []).map((item) => [itemKey(item), item.valor_unitario || ""]),
          ),
        );
        setProcessed(null);
        setDownload(null);
        setDocumentStructure(null);
        setDocumentNodes([]);
        setDocumentBlockIds([]);
        setMiniBoxAlignments({});
        setProposalColumnWidths(defaultProposalColumnWidths(false));
        setStructureError("");
        const review = payload.description_review;
        const verification = payload.pncp_items_check;
        setIdentifyMessage({
          kind: verification?.has_divergence || verification?.api_available === false
            ? "warning"
            : "success",
          text: `${payload.items.length} item(ns) encontrado(s).${
            review ? ` ${review.message}` : ""
          }`,
        });
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setIdentifyMessage({
          kind: "error",
          text: "Não foi possível consultar o edital. Verifique o link informado e tente novamente.",
        });
      }
    }, 450);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [pncpLink, itemSelection]);

  const selectedCountText = useMemo(() => {
    const total = identified?.items.length || 0;
    return `${selectedKeys.size} de ${total} itens selecionados`;
  }, [identified?.items.length, selectedKeys.size]);

  const toggleItem = (key: string) => {
    resetProcessedTemplateState();
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const updateUnitValue = (key: string, value: string) => {
    const numericValue = sanitizeMoneyInput(value);
    resetProcessedTemplateState();
    setUnitValues((current) => ({ ...current, [key]: numericValue }));
    if (numericValue) {
      setSelectedKeys((current) => new Set(current).add(key));
    }
  };

  const normalizeUnitValue = (key: string) => {
    const normalized = normalizeMoney(unitValues[key] || "");
    if (normalized) {
      setUnitValues((current) => ({ ...current, [key]: normalized }));
    }
  };

  const validate = (): string | null => {
    if (!isValidPncpUrl(pncpLink)) return "Informe uma URL válida do domínio pncp.gov.br.";
    if (!selectedResponsibleId) return "Selecione um responsável pela proposta.";
    if (!selectedTemplateId && !customTemplate) return "Selecione um template disponível.";
    if (!selectedKeys.size) return "Selecione pelo menos um item para a proposta.";
    for (const key of selectedKeys) {
      if (parseMoneyToCents(unitValues[key] || "") === null) {
        return "Informe um valor monetário válido para todos os itens selecionados.";
      }
    }
    return null;
  };

  const process = async (event: React.FormEvent) => {
    event.preventDefault();
    if (processing) return;
    const validationError = validate();
    if (validationError) {
      setMessage({ kind: "warning", text: validationError });
      return;
    }
    const processVersion = ++processVersionRef.current;
    generationVersionRef.current += 1;
    setGenerating(false);
    setDownload(null);
    setProcessing(true);
    setMessage({ kind: "info", text: "Processando proposta..." });
    try {
      const body = new FormData();
      body.append("pncp_link", normalizePncpUrl(pncpLink) || pncpLink.trim());
      body.append("responsible_id", selectedResponsibleId);
      body.append("wanted_items", selectedKeysAsText(selectedKeys));
      body.append("preset_brand", brand.trim());
      if (customTemplate) body.append("template_file", customTemplate);
      else body.append("template_choice", selectedTemplateId);

      const response = await processProposal(body);
      if (processVersion !== processVersionRef.current) return;
      const values = unitValues;
      const selectedItems = response.items
        .filter((item) => selectedKeys.has(itemKey(item)))
        .map((item) => {
          const normalized = normalizeMoney(values[itemKey(item)] || "") || "";
          return applyCommercialData(item, brand.trim(), normalized);
        });
      if (!selectedItems.length) {
        throw new Error("Os itens selecionados não foram encontrados no documento processado.");
      }
      setProcessed({ response, items: selectedItems });
      setDownload(null);
      setDocumentStructure(null);
      setDocumentNodes([]);
      setDocumentBlockIds([]);
      setMiniBoxAlignments({});
      setProposalColumnWidths(defaultProposalColumnWidths(
        selectedItems.some((item) => Boolean(String(item.lote || "").trim())),
      ));
      setStructureError("");
      setStructureLoading(true);
      try {
        const structure = await getDocxStructure(response.template_ref);
        if (processVersion !== processVersionRef.current) return;
        setDocumentStructure(structure);
        setDocumentNodes(structure.nodes.map((node) => ({ ...node })));
        setDocumentBlockIds(
          createDocumentBlockOrder(structure.nodes, structure.generated_table_block.id),
        );
        setMiniBoxAlignments(Object.fromEntries(
          structure.nodes
            .filter((node) => node.type === "MINI_BOX")
            .map((node) => [node.id, node.text_align]),
        ));
        setMessage({
          kind: "success",
          text: `Proposta processada com sucesso. ${selectedItems.length} item(ns) preparado(s). Modelo ${response.template_source === "upload" ? "avulso" : "cadastrado"} aplicado: ${response.template_name}.`,
        });
      } catch (structureFailure) {
        if (processVersion !== processVersionRef.current) return;
        const errorText = structureFailure instanceof Error
          ? structureFailure.message
          : "Não foi possível analisar os blocos do modelo Word.";
        setStructureError(errorText);
        setMessage({
          kind: "warning",
          text: `A proposta foi processada, mas a estrutura do modelo não pôde ser carregada. ${errorText}`,
        });
      } finally {
        if (processVersion === processVersionRef.current) setStructureLoading(false);
      }
    } catch (error) {
      if (processVersion !== processVersionRef.current) return;
      setMessage({
        kind: "error",
        text: error instanceof Error
          ? error.message
          : "Não foi possível processar a proposta. Nenhum dado anterior foi alterado.",
      });
    } finally {
      if (processVersion === processVersionRef.current) setProcessing(false);
    }
  };

  const invalidateGeneratedDocument = () => {
    generationVersionRef.current += 1;
    setGenerating(false);
    setDownload(null);
  };

  const updateProcessedItem = (
    index: number,
    field: "marca" | "valor_unitario",
    value: string,
  ) => {
    setProcessed((current) => {
      if (!current) return current;
      const items = current.items.map((item, itemIndex) => {
        if (index !== itemIndex) return item;
        const updated = { ...item, [field]: value };
        updated.valor_total = calculateItemTotal(updated.quantidade, updated.valor_unitario);
        return updated;
      });
      return { ...current, items };
    });
    invalidateGeneratedDocument();
  };

  const preparedItems = (): ProposalItem[] =>
    (processed?.items || []).map((item) => ({
      ...item,
      marca: item.marca.trim(),
      valor_unitario: normalizeMoney(item.valor_unitario) || item.valor_unitario,
      valor_total: calculateItemTotal(item.quantidade, item.valor_unitario),
    }));

  const orderedMiniBoxIds = documentStructure
    ? miniBoxOrderFromDocumentOrder(
        documentBlockIds,
        documentStructure.generated_table_block.id,
      )
    : undefined;

  const orderedDocumentBlockIds = documentStructure
    ? documentBlockIds
    : undefined;

  const updateDocumentOrder = (order: string[]) => {
    setDocumentBlockIds(order);
    invalidateGeneratedDocument();
  };

  const commitDocumentOrder = () => {
    setMessage({
      kind: "info",
      text: "Composição atualizada e refletida na pré-visualização.",
    });
  };

  const updateMiniBoxAlignment = (id: string, alignment: MiniBoxTextAlign) => {
    setMiniBoxAlignments((current) => ({ ...current, [id]: alignment }));
    invalidateGeneratedDocument();
    setMessage({
      kind: "info",
      text: alignment === "center"
        ? "Texto do mini-box centralizado e refletido na pré-visualização."
        : "Alinhamento do mini-box atualizado na pré-visualização.",
    });
  };

  const resetMiniBoxAlignments = (alignments: Record<string, MiniBoxTextAlign>) => {
    setMiniBoxAlignments(alignments);
    invalidateGeneratedDocument();
  };

  const validateDocument = (): boolean => {
    if (!processed) return false;
    if (!selectedResponsibleId) {
      setMessage({ kind: "warning", text: "Selecione um responsável pela proposta." });
      return false;
    }
    if (
      processed.items.some(
        (item) => parseMoneyToCents(item.valor_unitario || "") === null,
      )
    ) {
      setMessage({ kind: "warning", text: "Revise os valores unitários antes de gerar o Word." });
      return false;
    }
    return true;
  };

  const generate = async () => {
    if (!processed || generating || !validateDocument()) return;
    const generationVersion = ++generationVersionRef.current;
    setGenerating(true);
    setDownload(null);
    setMessage({ kind: "info", text: "Gerando documento Word..." });
    try {
      const response = await generateProposal(
        preparedItems(),
        processed.response.template_ref,
        processed.response.source_name,
        selectedResponsibleId,
        processed.response.commercial_terms,
        orderedMiniBoxIds,
        orderedDocumentBlockIds,
        miniBoxAlignments,
        proposalColumnWidths,
      );
      if (generationVersion !== generationVersionRef.current) return;
      setDownload({ url: response.download_url, filename: response.filename });
      setMessage({ kind: "success", text: "Documento Word gerado com sucesso." });
    } catch (error) {
      if (generationVersion !== generationVersionRef.current) return;
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível gerar o documento Word.",
      });
    } finally {
      if (generationVersion === generationVersionRef.current) setGenerating(false);
    }
  };

  return (
    <section className="workspace-section proposal-retro" aria-label="Gerar proposta">
      <form className="proposal-form retro-proposal-form" onSubmit={process}>
        <div className="retro-url-field span-all">
          <input
            id="pncp-link"
            type="text"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            aria-label="URL do edital no PNCP"
            maxLength={500}
            value={pncpLink}
            placeholder="https://pncp.gov.br/app/editais/CNPJ/ANO/SEQUENCIAL"
            onChange={(event) => {
              resetProcessedTemplateState();
              onPncpLinkChange(event.target.value);
            }}
            onBlur={(event) => {
              const normalized = normalizePncpUrl(event.target.value);
              if (normalized) onPncpLinkChange(normalized);
            }}
          />
          <label htmlFor="pncp-link">INSIRA A URL PNCP</label>
        </div>

        <div className="retro-main-grid span-all">
          <div className="proposal-fields retro-fields-panel">
          <label>
            Marca
            <input
              maxLength={120}
              value={brand}
              placeholder="Ex.: Goldflex"
              onChange={(event) => {
                resetProcessedTemplateState();
                setBrand(event.target.value);
              }}
              onBlur={() => setBrand((current) => current.trim())}
            />
          </label>
          <label>
            Responsável
            <div className="field-with-action">
              <select
                value={selectedResponsibleId}
              onChange={(event) => {
                  onSelectedResponsibleChange(event.target.value);
                  invalidateGeneratedDocument();
                }}
              >
                {!responsibles.length && <option value="">Nenhum responsável cadastrado</option>}
                {responsibles.map((responsible) => (
                  <option value={responsible.id} key={responsible.id}>
                    {responsible.nome_completo}
                  </option>
                ))}
              </select>
              <button
                className="retro-edit-button"
                type="button"
                title="Gerenciar responsáveis"
                aria-label="Gerenciar responsáveis"
                onClick={onOpenResponsibles}
              >
                <Pencil size={22} strokeWidth={2.4} />
              </button>
            </div>
          </label>
          <label>
            Template
            <div className="field-with-action">
              <select
                value={selectedTemplateId}
                onChange={(event) => {
                  resetProcessedTemplateState();
                  onSelectedTemplateChange(event.target.value);
                }}
              >
                {!templates.length && <option value="">Nenhum template cadastrado</option>}
                {templates.map((template) => (
                  <option value={template.id} key={template.id}>
                    {template.display_name || template.name}
                  </option>
                ))}
              </select>
              <button
                className="retro-edit-button"
                type="button"
                title="Gerenciar templates"
                aria-label="Gerenciar templates"
                onClick={onOpenTemplates}
              >
                <Pencil size={22} strokeWidth={2.4} />
              </button>
            </div>
          </label>

            <div className="template-utilities">
              {selectedTemplate ? (
                <a
                  className="button button-secondary"
                  href={selectedTemplate.download_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <ExternalLink size={16} />
                  Abrir template
                </a>
              ) : (
                <span className="muted-text">Nenhum template cadastrado.</span>
              )}
              <div className={`custom-template${customTemplate ? " is-active" : ""}`}>
                <span>{customTemplate?.name || "Template avulso"}</span>
                <div className="custom-template-actions">
                  <button
                    className="button button-secondary"
                    type="button"
                    onClick={() => customTemplateRef.current?.click()}
                  >
                    <Upload size={16} />
                    Anexar .docx
                  </button>
                  {customTemplate && (
                    <button
                      className="button button-secondary custom-template-clear"
                      type="button"
                      title="Remover template avulso"
                      aria-label="Remover template avulso"
                      onClick={() => {
                        setCustomTemplate(null);
                        if (customTemplateRef.current) customTemplateRef.current.value = "";
                        resetProcessedTemplateState();
                        setMessage({
                          kind: "info",
                          text: "Template avulso removido. O template cadastrado está ativo.",
                        });
                      }}
                    >
                      <X size={16} />
                    </button>
                  )}
                </div>
                <input
                  ref={customTemplateRef}
                  type="file"
                  accept=".docx"
                  hidden
                  onChange={(event) => {
                    const file = event.target.files?.[0] || null;
                    if (!file) return;
                    const error = validateTemplateFile(file);
                    if (error) {
                      event.target.value = "";
                      setMessage({ kind: "warning", text: error });
                      return;
                    }
                    setCustomTemplate(file);
                    resetProcessedTemplateState();
                    setMessage({ kind: "success", text: "Template avulso selecionado para esta proposta." });
                  }}
                />
              </div>
            </div>
          </div>

          <section className="items-section retro-items-panel" aria-labelledby="items-heading">
          <div className="items-heading">
            <div>
              <h3 id="items-heading">Itens do edital</h3>
            </div>
            <div className="selection-count">{selectedCountText}</div>
          </div>
          <StatusMessage message={identifyMessage} compact />
          <div className="data-table-wrap item-table-wrap">
            {identified?.items.length ? (
              <table className="data-table item-table">
                <thead>
                  <tr>
                    <th aria-label="Seleção" />
                    <th>Identificação</th>
                    <th>Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {identified.items.map((item) => {
                    const key = itemKey(item);
                    const selected = selectedKeys.has(key);
                    return (
                      <tr className={selected ? "is-selected" : ""} key={key}>
                        <td className="retro-select-cell">
                          <input
                            type="checkbox"
                            checked={selected}
                            aria-label={`Selecionar item ${key}`}
                            onChange={() => toggleItem(key)}
                          />
                        </td>
                        <td className="retro-identification-cell" title={item.descricao}>
                          <strong>
                            {showLot && item.lote ? `LOTE ${item.lote} · ` : ""}
                            ITEM {item.item}
                          </strong>
                          <span>{item.categoria || "Item do edital"}</span>
                        </td>
                        <td className="retro-value-cell">
                          <input
                            className="money-input"
                            inputMode="decimal"
                            value={unitValues[key] || ""}
                            placeholder="R$ 0,00"
                            onChange={(event) => updateUnitValue(key, event.target.value)}
                            onBlur={() => normalizeUnitValue(key)}
                          />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <div className="empty-state">
                Informe o link do PNCP para carregar os itens reais do edital.
              </div>
            )}
          </div>
          </section>
        </div>

        <div className="proposal-submit span-all">
          <span>Somente os itens selecionados serão incluídos na proposta.</span>
          <button className="button button-primary" type="submit" disabled={processing}>
            <FileOutput size={18} />
            {processing ? "Processando proposta..." : "Extrair tabelas e aplicar valores"}
          </button>
        </div>
      </form>

      <section className="result-section" aria-labelledby="result-heading">
        <div className="result-heading">
          <div>
            <h3 id="result-heading">Resultado da proposta</h3>
            <p>Composição e documento final.</p>
          </div>
          <div className="result-actions">
            {processed && (
              <button
                className="button button-primary"
                type="button"
                disabled={generating || structureLoading}
                onClick={generate}
              >
                <FileOutput size={17} />
                {generating ? "Gerando..." : "Gerar Word"}
              </button>
            )}
            {download && (
              <a className="button button-success" href={download.url} download>
                <Download size={17} />
                Baixar Word
              </a>
            )}
          </div>
        </div>
        {message && <StatusMessage message={message} />}
        {processed && structureLoading && (
          <div className="docx-structure-loading" role="status">
            Analisando a estrutura do modelo Word...
          </div>
        )}
        {processed && structureError && !structureLoading && (
          <StatusMessage message={{ kind: "warning", text: structureError }} compact />
        )}
        {processed && documentStructure && !structureLoading && (
          <DocxReorderBoard
            structure={documentStructure}
            nodes={documentNodes}
            blockOrder={documentBlockIds}
            alignments={miniBoxAlignments}
            disabled={generating}
            onOrderChange={updateDocumentOrder}
            onOrderCommit={commitDocumentOrder}
            onAlignmentChange={updateMiniBoxAlignment}
            onAlignmentsReset={resetMiniBoxAlignments}
            renderPreview={(previewOrder) => (
              <ProposalLivePreview
                nodes={documentNodes}
                blockOrder={previewOrder}
                generatedTable={documentStructure.generated_table_block}
                items={processed.items}
                commercialTerms={processed.response.commercial_terms}
                responsible={selectedResponsible}
                miniBoxAlignments={miniBoxAlignments}
                columnWidths={proposalColumnWidths}
                onColumnWidthsChange={(widths) => {
                  setProposalColumnWidths(widths);
                  invalidateGeneratedDocument();
                }}
              />
            )}
          />
        )}
        {processed && (
          <div className="data-table-wrap result-table-wrap">
            <table className="data-table result-table">
              <thead>
                <tr>
                  {processed.items.some((item) => item.lote) && <th>Lote</th>}
                  <th>Item</th>
                  <th>Qtd.</th>
                  <th>UND</th>
                  <th>Descrição</th>
                  <th>Marca</th>
                  <th>Valor unitário</th>
                  <th>Valor total</th>
                </tr>
              </thead>
              <tbody>
                {processed.items.map((item, index) => (
                  <tr key={itemKey(item)}>
                    {processed.items.some((row) => row.lote) && <td>{item.lote}</td>}
                    <td>{item.item}</td>
                    <td>{item.quantidade}</td>
                    <td>UND</td>
                    <td className="description-cell">{item.descricao}</td>
                    <td>
                      <input
                        value={item.marca}
                        maxLength={120}
                        onChange={(event) => updateProcessedItem(index, "marca", event.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="money-input"
                        inputMode="decimal"
                        value={item.valor_unitario}
                        onChange={(event) =>
                          updateProcessedItem(
                            index,
                            "valor_unitario",
                            sanitizeMoneyInput(event.target.value),
                          )
                        }
                        onBlur={() => {
                          const normalized = normalizeMoney(item.valor_unitario);
                          if (normalized) updateProcessedItem(index, "valor_unitario", normalized);
                        }}
                      />
                    </td>
                    <td>{item.valor_total || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {download && <div className="generated-file">Arquivo: {download.filename}</div>}
      </section>
    </section>
  );
}
