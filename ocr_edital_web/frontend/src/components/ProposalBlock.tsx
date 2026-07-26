import { useEffect, useMemo, useRef, useState } from "react";
import {
  Download,
  Eye,
  ExternalLink,
  FileOutput,
  Pencil,
  RefreshCw,
  Upload,
} from "lucide-react";
import {
  generateProposal,
  identifyItems,
  previewProposal,
  processProposal,
} from "../api";
import type {
  IdentifyResponse,
  ProcessResponse,
  ProposalPreviewResponse,
  ProposalItem,
  Responsible,
  Template,
  UiMessage,
} from "../types";
import {
  calculateItemTotal,
  isValidPncpUrl,
  itemKey,
  normalizeMoney,
  normalizePncpUrl,
  parseMoneyToCents,
  validateTemplateFile,
} from "../utils";
import { StatusMessage } from "./StatusMessage";

interface ProposalBlockProps {
  pncpLink: string;
  onPncpLinkChange: (link: string) => void;
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
  const [previewing, setPreviewing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [filePreview, setFilePreview] = useState<ProposalPreviewResponse | null>(null);
  const [download, setDownload] = useState<{ url: string; filename: string } | null>(null);

  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
  const showLot = Boolean(identified?.items.some((item) => String(item.lote || "").trim()));

  useEffect(() => {
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

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIdentifyMessage({ kind: "info", text: "Consultando edital..." });
      try {
        const payload = await identifyItems(normalizedLink, controller.signal);
        setIdentified(payload);
        setSelectedKeys(new Set());
        setUnitValues(
          Object.fromEntries(
            (payload.items || []).map((item) => [itemKey(item), item.valor_unitario || ""]),
          ),
        );
        setProcessed(null);
        setFilePreview(null);
        setDownload(null);
        const review = payload.description_review;
        setIdentifyMessage({
          kind: payload.pncp_items_check?.has_divergence ? "warning" : "success",
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
  }, [pncpLink]);

  const selectedCountText = useMemo(() => {
    const total = identified?.items.length || 0;
    return `${selectedKeys.size} de ${total} itens selecionados`;
  }, [identified?.items.length, selectedKeys.size]);

  const toggleItem = (key: string) => {
    setSelectedKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const updateUnitValue = (key: string, value: string) => {
    setUnitValues((current) => ({ ...current, [key]: value }));
    if (value.trim()) {
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
    setProcessing(true);
    setMessage({ kind: "info", text: "Processando proposta..." });
    try {
      const body = new FormData();
      body.append("pncp_link", normalizePncpUrl(pncpLink) || pncpLink.trim());
      body.append("responsible_id", selectedResponsibleId);
      body.append("template_choice", selectedTemplateId);
      body.append("wanted_items", selectedKeysAsText(selectedKeys));
      body.append("preset_brand", brand.trim());
      if (customTemplate) body.append("template_file", customTemplate);

      const response = await processProposal(body);
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
      setFilePreview(null);
      setDownload(null);
      setMessage({
        kind: "success",
        text: `Proposta processada com sucesso. ${selectedItems.length} item(ns) preparado(s).`,
      });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error
          ? error.message
          : "Não foi possível processar a proposta. Nenhum dado anterior foi alterado.",
      });
    } finally {
      setProcessing(false);
    }
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
    setFilePreview(null);
    setDownload(null);
  };

  const preparedItems = (): ProposalItem[] =>
    (processed?.items || []).map((item) => ({
      ...item,
      marca: item.marca.trim(),
      valor_unitario: normalizeMoney(item.valor_unitario) || item.valor_unitario,
      valor_total: calculateItemTotal(item.quantidade, item.valor_unitario),
    }));

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

  const previewFile = async () => {
    if (!processed || previewing || !validateDocument()) return;
    setPreviewing(true);
    setMessage({ kind: "info", text: "Gerando pré-visualização fiel do arquivo..." });
    try {
      const response = await previewProposal(
        preparedItems(),
        processed.response.template_ref,
        processed.response.source_name,
        selectedResponsibleId,
        processed.response.commercial_terms,
      );
      setFilePreview(response);
      setDownload(null);
      setMessage({
        kind: "success",
        text: response.cached
          ? "Pré-visualização atualizada."
          : "Pré-visualização gerada com sucesso.",
      });
    } catch (error) {
      setFilePreview(null);
      setMessage({
        kind: "error",
        text: error instanceof Error
          ? error.message
          : "Não foi possível gerar a pré-visualização do arquivo.",
      });
    } finally {
      setPreviewing(false);
    }
  };

  const generate = async () => {
    if (!processed || !filePreview || generating || !validateDocument()) return;
    setGenerating(true);
    setMessage({ kind: "info", text: "Gerando documento Word..." });
    try {
      const response = await generateProposal(
        preparedItems(),
        processed.response.template_ref,
        processed.response.source_name,
        selectedResponsibleId,
        processed.response.commercial_terms,
      );
      setDownload({ url: response.download_url, filename: response.filename });
      setMessage({ kind: "success", text: "Documento Word gerado com sucesso." });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível gerar o documento Word.",
      });
    } finally {
      setGenerating(false);
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
            onChange={(event) => onPncpLinkChange(event.target.value)}
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
              onChange={(event) => setBrand(event.target.value)}
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
                  setFilePreview(null);
                  setDownload(null);
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
                  onSelectedTemplateChange(event.target.value);
                  setFilePreview(null);
                  setDownload(null);
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
              <div className="custom-template">
                <span>{customTemplate?.name || "Template avulso"}</span>
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => customTemplateRef.current?.click()}
                >
                  <Upload size={16} />
                  Anexar .docx
                </button>
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
                    setFilePreview(null);
                    setDownload(null);
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
            <p>Pré-visualização, validações e documento gerado.</p>
          </div>
          <div className="result-actions">
            {processed && (
              <button
                className="button button-primary"
                type="button"
                disabled={previewing || generating}
                onClick={previewFile}
              >
                {filePreview ? <RefreshCw size={17} /> : <Eye size={17} />}
                {previewing
                  ? "Preparando prévia..."
                  : filePreview
                    ? "Atualizar prévia"
                    : "Pré-visualizar arquivo"}
              </button>
            )}
            {filePreview && (
              <button
                className="button button-secondary"
                type="button"
                disabled={generating || previewing}
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
        {filePreview && (
          <section className="proposal-file-preview" aria-labelledby="proposal-file-preview-heading">
            <div className="proposal-file-preview-heading">
              <h4 id="proposal-file-preview-heading">Pré-visualização do arquivo</h4>
              <a
                className="button button-secondary"
                href={filePreview.preview_url}
                target="_blank"
                rel="noreferrer"
              >
                <ExternalLink size={16} />
                Abrir
              </a>
            </div>
            <iframe
              src={filePreview.preview_url}
              title="Pré-visualização do documento da proposta"
            />
          </section>
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
                        value={item.valor_unitario}
                        onChange={(event) =>
                          updateProcessedItem(index, "valor_unitario", event.target.value)
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
