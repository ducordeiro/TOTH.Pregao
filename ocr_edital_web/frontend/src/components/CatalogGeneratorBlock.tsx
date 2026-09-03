import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Check,
  Database,
  Download,
  ExternalLink,
  FileArchive,
  LoaderCircle,
  Play,
  Plus,
  Save,
  SlidersHorizontal,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { createCatalogGeneratorJob, exportGeneratedCatalog, getCatalogGeneratorJob, saveCatalogTechnicalRepertoire } from "../api";
import type {
  CatalogEvidenceObservation,
  CatalogExportFile,
  CatalogGeneratorJob,
  CatalogTechnicalParameter,
  CatalogTechnicalRepertoireInput,
  GeneratedCatalogItem,
  OpportunityItemSelection,
  Template,
} from "../types";
import { opportunityItemKey, selectionForLink } from "../opportunitySelection";
import { validateTemplateFile } from "../utils";

interface CatalogGeneratorBlockProps {
  pncpLink: string;
  onPncpLinkChange: (value: string) => void;
  itemSelection?: OpportunityItemSelection | null;
  templates: Template[];
  selectedTemplateId: string;
  onSelectedTemplateChange: (id: string) => void;
}

const humanizeCatalogStatus = (value: string) => value.replaceAll("_", " ");

const catalogExportLabel = (kind: string) => {
  if (kind === "docx") return "Catálogo DOCX";
  if (kind === "pdf") return "Catálogo PDF";
  return "Auditoria " + kind.toUpperCase();
};

type TechnicalParameterDraft = Omit<CatalogTechnicalParameter, "valor_requerido" | "valor_minimo" | "valor_maximo"> & {
  valor_requerido: string;
  valor_minimo: string;
  valor_maximo: string;
};

const technicalParameterId = () => (
  globalThis.crypto?.randomUUID?.().replaceAll("-", "")
  || `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`.slice(0, 32).padEnd(32, "0")
);

const newTechnicalParameter = (): TechnicalParameterDraft => ({
  id: technicalParameterId(),
  componente: "",
  atributo: "",
  comparacao: "intervalo",
  valor_requerido: "",
  valor_minimo: "",
  valor_maximo: "",
  unidade: "",
  valor_requerido_texto: "",
  valor_atendido_texto: "",
  evidencia: "",
});

const technicalParameterDraft = (parameter: CatalogTechnicalParameter): TechnicalParameterDraft => ({
  ...parameter,
  valor_requerido: parameter.valor_requerido === undefined ? "" : String(parameter.valor_requerido),
  valor_minimo: parameter.valor_minimo === undefined ? "" : String(parameter.valor_minimo),
  valor_maximo: parameter.valor_maximo === undefined ? "" : String(parameter.valor_maximo),
});

const catalogObservation = (item: GeneratedCatalogItem): CatalogEvidenceObservation => (
  item.observacao_repertorio || {
    status: item.modelo_referencia ? "evidencia_parcial" : "sem_repertorio",
    titulo: item.modelo_referencia
      ? "Foram encontradas evidências parciais"
      : "Não foi encontrado repertório para o item",
    descricao: item.modelo_referencia
      ? "Esta análise foi criada antes da auditoria por componentes e precisa ser reavaliada."
      : "Não há dados técnicos cadastrados que permitam validar os componentes solicitados.",
    evidencias: [],
    faltantes: item.analise_aderencia?.pendencias || ["Cadastre os parâmetros técnicos do item."],
    fonte: item.modelo_referencia?.fonte || "",
  }
);

export function CatalogGeneratorBlock({
  pncpLink,
  onPncpLinkChange,
  itemSelection,
  templates,
  selectedTemplateId,
  onSelectedTemplateChange,
}: CatalogGeneratorBlockProps) {
  const templateInputRef = useRef<HTMLInputElement>(null);
  const [job, setJob] = useState<CatalogGeneratorJob | null>(null);
  const [items, setItems] = useState<GeneratedCatalogItem[]>([]);
  const [exports, setExports] = useState<Record<string, CatalogExportFile>>({});
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [starting, setStarting] = useState(false);
  const [customTemplate, setCustomTemplate] = useState<File | null>(null);
  const [editingRepertoireItemId, setEditingRepertoireItemId] = useState("");
  const [repertoireProductName, setRepertoireProductName] = useState("");
  const [repertoireCoverageComplete, setRepertoireCoverageComplete] = useState(false);
  const [technicalParameters, setTechnicalParameters] = useState<TechnicalParameterDraft[]>([]);
  const [savingRepertoire, setSavingRepertoire] = useState(false);
  const requestVersion = useRef(0);
  const exportVersion = useRef(0);
  const selection = selectionForLink(itemSelection, pncpLink);
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
  const selectedTemplateVersion = selectedTemplate
    ? `${selectedTemplate.id}:${selectedTemplate.size}:${selectedTemplate.updated_at}`
    : "";
  const customTemplateVersion = customTemplate
    ? `${customTemplate.name}:${customTemplate.size}:${customTemplate.lastModified}`
    : "";

  useEffect(() => {
    requestVersion.current += 1;
    exportVersion.current += 1;
    setJob(null);
    setItems([]);
    setExports({});
    setError("");
    setStarting(false);
    setExporting(false);
    setEditingRepertoireItemId("");
    setTechnicalParameters([]);
    setSavingRepertoire(false);
  }, [pncpLink, itemSelection, selectedTemplateVersion, customTemplateVersion]);

  useEffect(() => {
    if (!job || !["queued", "processing"].includes(job.status)) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      getCatalogGeneratorJob(job.id)
        .then((updated) => {
          if (cancelled) return;
          setJob(updated);
          if (updated.result) setItems(updated.result.items);
          if (updated.status === "failed") setError(updated.error);
        })
        .catch((reason) => {
          if (!cancelled) setError(reason instanceof Error ? reason.message : "Falha ao acompanhar o processamento.");
        });
    }, 900);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [job?.id, job?.status]);

  const stageIndex = useMemo(
    () => Math.max(0, job?.stages.findIndex((stage) => stage.id === job.stage) ?? 0),
    [job],
  );

  const start = async () => {
    if (starting) return;
    if (!selectedTemplateId && !customTemplate) {
      setError("Selecione ou anexe um template Word para gerar o catálogo.");
      return;
    }
    const version = ++requestVersion.current;
    exportVersion.current += 1;
    setStarting(true);
    setExporting(false);
    setJob(null);
    setError("");
    setExports({});
    setItems([]);
    try {
      const created = await createCatalogGeneratorJob(
        pncpLink,
        selection?.items.map(opportunityItemKey),
        customTemplate ? undefined : selectedTemplateId,
        customTemplate || undefined,
      );
      if (version === requestVersion.current) setJob(created);
    } catch (reason) {
      if (version === requestVersion.current) setError(reason instanceof Error ? reason.message : "Não foi possível iniciar o catálogo.");
    } finally {
      if (version === requestVersion.current) setStarting(false);
    }
  };

  const updateItem = (id: string, field: keyof GeneratedCatalogItem, value: string) => {
    exportVersion.current += 1;
    setExporting(false);
    setExports({});
    setItems((current) => current.map((item) => {
      if (item.id !== id) return item;
      const updated = {
        ...item,
        [field]: value,
        ...(field === "descricao" ? { especificacao_tecnica: value } : {}),
      };
      const missing = [
        ["descricao", "descrição"],
        ["quantidade", "quantidade"],
        ["unidade", "unidade"],
      ].filter(([key]) => !String(updated[key as keyof GeneratedCatalogItem] || "").trim())
        .map(([, label]) => label);
      const invalidatesAnalysis = [
        "produto",
        "descricao",
        "especificacao_tecnica",
        "criterios_aceitacao",
        "observacoes",
        "categoria",
        "subcategoria",
      ].includes(field);
      return {
        ...updated,
        campos_ausentes: missing,
        status_evidencia: missing.length ? "incompleto" : "confirmado",
        analise_desatualizada: invalidatesAnalysis || updated.analise_desatualizada,
      };
    }));
  };

  const selectCustomTemplate = (file: File) => {
    const validationError = validateTemplateFile(file);
    if (validationError) {
      setError(validationError);
      if (templateInputRef.current) templateInputRef.current.value = "";
      return;
    }
    setError("");
    setCustomTemplate(file);
    onSelectedTemplateChange("");
  };

  const runExport = async () => {
    if (!job) return;
    const version = requestVersion.current;
    const currentExportVersion = ++exportVersion.current;
    setExporting(true);
    setError("");
    try {
      const response = await exportGeneratedCatalog(job.id, items);
      if (version === requestVersion.current && currentExportVersion === exportVersion.current) {
        setItems(response.items);
        setExports(response.exports);
      }
    } catch (reason) {
      if (version === requestVersion.current && currentExportVersion === exportVersion.current) {
        setError(reason instanceof Error ? reason.message : "Não foi possível exportar o catálogo.");
      }
    } finally {
      if (version === requestVersion.current && currentExportVersion === exportVersion.current) {
        setExporting(false);
      }
    }
  };

  const openRepertoireEditor = (item: GeneratedCatalogItem) => {
    const saved = item.repertorio_usuario;
    setEditingRepertoireItemId(item.id);
    setRepertoireProductName(saved?.produto_nome || item.produto || `Item ${item.numero}`);
    setRepertoireCoverageComplete(saved?.cobertura_completa || false);
    setTechnicalParameters(
      saved?.parametros.length
        ? saved.parametros.map(technicalParameterDraft)
        : [newTechnicalParameter()],
    );
    setError("");
  };

  const updateTechnicalParameter = (
    id: string,
    field: keyof TechnicalParameterDraft,
    value: string,
  ) => {
    setTechnicalParameters((current) => current.map((parameter) => (
      parameter.id === id ? { ...parameter, [field]: value } : parameter
    )));
  };

  const saveTechnicalRepertoire = async (item: GeneratedCatalogItem) => {
    if (!job || savingRepertoire) return;
    const input: CatalogTechnicalRepertoireInput = {
      produto_nome: repertoireProductName,
      cobertura_completa: repertoireCoverageComplete,
      parametros: technicalParameters.map((parameter) => (
        parameter.comparacao === "intervalo"
          ? {
              id: parameter.id,
              componente: parameter.componente,
              atributo: parameter.atributo,
              comparacao: parameter.comparacao,
              valor_requerido: Number(parameter.valor_requerido.replace(",", ".")),
              valor_minimo: Number(parameter.valor_minimo.replace(",", ".")),
              valor_maximo: Number(parameter.valor_maximo.replace(",", ".")),
              unidade: parameter.unidade,
              evidencia: parameter.evidencia,
            }
          : {
              id: parameter.id,
              componente: parameter.componente,
              atributo: parameter.atributo,
              comparacao: parameter.comparacao,
              valor_requerido_texto: parameter.valor_requerido_texto,
              valor_atendido_texto: parameter.valor_atendido_texto,
              evidencia: parameter.evidencia,
            }
      )),
    };
    setSavingRepertoire(true);
    setError("");
    try {
      const updated = await saveCatalogTechnicalRepertoire(job.id, item.id, input);
      setJob(updated);
      setItems(updated.result?.items || []);
      setExports({});
      setEditingRepertoireItemId("");
      setTechnicalParameters([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível salvar a régua técnica.");
    } finally {
      setSavingRepertoire(false);
    }
  };

  const result = job?.result;
  const currentCatalogMetrics = useMemo(() => {
    const current = items.filter((item) => !item.analise_desatualizada);
    return {
      modelos: new Set(current.map((item) => item.modelo_referencia?.id).filter(Boolean)).size,
      semModelo: current.filter((item) => !item.modelo_referencia).length,
      divergencias: current.filter((item) => item.status_catalogo === "bloqueado_por_divergencia").length,
      reanalises: items.length - current.length,
    };
  }, [items]);
  const currentValidation = useMemo(() => {
    const incompletos = items.filter((item) => item.campos_ausentes.length > 0).length;
    const conflitos = items.filter((item) => item.conflitos.length > 0).length;
    const avisos = [
      ...(incompletos ? [`${incompletos} item(ns) possuem campos obrigatórios ausentes.`] : []),
      ...(conflitos ? [`${conflitos} item(ns) possuem divergências entre fontes.`] : []),
      ...(!items.length ? ["Nenhum item foi identificado nas fontes disponíveis."] : []),
    ];
    return { incompletos, conflitos, avisos };
  }, [items]);
  const currentWarnings = result
    ? [
        ...result.warnings.filter((warning) => !result.validation.avisos.includes(warning)),
        ...currentValidation.avisos,
      ]
    : [];
  return (
    <section className="catalog-generator" aria-label="Gerador de catálogo">
      <form className="catalog-generator-input" onSubmit={(event) => { event.preventDefault(); void start(); }}>
        <label htmlFor="catalog-generator-link">Link do edital no PNCP</label>
        <div className="catalog-generator-link-row">
          <input
            id="catalog-generator-link"
            type="url"
            value={pncpLink}
            onChange={(event) => onPncpLinkChange(event.target.value)}
            placeholder="https://pncp.gov.br/app/editais/..."
            required
          />
          <button className="button button-primary" type="submit" disabled={starting || job?.status === "processing" || job?.status === "queued" || selection?.items.length === 0}>
            <Play size={17} aria-hidden="true" /> {starting ? "Iniciando..." : selection ? "Processar seleção" : "Processar edital"}
          </button>
        </div>
        <div className="catalog-generator-template-row">
          <label htmlFor="catalog-generator-template">Template Word</label>
          <div className="catalog-generator-template-controls">
            <select
              id="catalog-generator-template"
              value={customTemplate ? "" : selectedTemplateId}
              onChange={(event) => {
                setCustomTemplate(null);
                if (templateInputRef.current) templateInputRef.current.value = "";
                onSelectedTemplateChange(event.target.value);
              }}
            >
              <option value="">
                {templates.length ? "Selecione um template" : "Nenhum template cadastrado"}
              </option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.display_name || template.name}
                </option>
              ))}
            </select>
            {selectedTemplate && (
              <a className="button button-secondary" href={selectedTemplate.download_url} target="_blank" rel="noreferrer">
                <ExternalLink size={16} aria-hidden="true" /> Abrir template
              </a>
            )}
            <div className={`custom-template catalog-generator-custom-template${customTemplate ? " is-active" : ""}`}>
              <span>{customTemplate?.name || "Template avulso"}</span>
              <div className="custom-template-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  onClick={() => templateInputRef.current?.click()}
                >
                  <Upload size={16} /> Anexar .docx
                </button>
                {customTemplate && (
                  <button
                    className="button button-secondary custom-template-clear"
                    type="button"
                    title="Remover template avulso"
                    aria-label="Remover template avulso"
                    onClick={() => {
                      setCustomTemplate(null);
                      if (templateInputRef.current) templateInputRef.current.value = "";
                    }}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            </div>
            <input
              ref={templateInputRef}
              type="file"
              accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) selectCustomTemplate(file);
              }}
            />
          </div>
          <small>Use o marcador {"{CATALOGO}"} no modelo para definir o ponto de inserção. Sem ele, o catálogo será acrescentado ao final.</small>
        </div>
      </form>

      {selection && (
        <section className="catalog-generator-selection" aria-label="Itens selecionados no detalhamento">
          <strong>{selection.items.length} item(ns) selecionado(s)</strong>
          <ul>
            {selection.items.map((item) => (
              <li key={opportunityItemKey(item)}>
                <span>Item {item.numero}{item.lote ? ` · Lote ${item.lote}` : ""}</span>
                <span>{item.descricao}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {job && (
        <section className="catalog-generator-progress" aria-live="polite">
          <div className="catalog-generator-progress-copy">
            <strong>{job.status === "ready" ? "Processamento concluído" : "Gerando catálogo"}</strong>
            <span>{job.progress}%</span>
          </div>
          <div className="catalog-generator-progress-track"><span style={{ width: `${job.progress}%` }} /></div>
          <ol className="catalog-generator-stages">
            {job.stages.map((stage, index) => (
              <li key={stage.id} className={index < stageIndex || job.status === "ready" ? "is-done" : index === stageIndex ? "is-current" : ""}>
                {index < stageIndex || job.status === "ready" ? <Check size={15} /> : index === stageIndex ? <LoaderCircle size={15} /> : <span />}
                {stage.label}
              </li>
            ))}
          </ol>
        </section>
      )}

      {error && <div className="status-message status-error"><AlertTriangle size={17} /> {error}</div>}

      {result && (
        <>
          <section className="catalog-generator-summary">
            <div>
              <span>Edital</span>
              <strong>{String(result.metadata.numero_compra || result.metadata.processo || "Não informado")}</strong>
              <small>{String(result.metadata.orgao || "Órgão não informado")}</small>
            </div>
            <div><span>Modalidade</span><strong>{String(result.metadata.modalidade || "Não informada")}</strong><small>{String(result.metadata.situacao || "Situação não informada")}</small></div>
            <div><span>Itens</span><strong>{items.length}</strong><small>{currentValidation.incompletos} pendência(s)</small></div>
            <div><span>Repertório estruturado</span><strong>{result.repertoire.structured_models} modelos</strong><small>{currentCatalogMetrics.modelos} localizado(s) nesta análise</small></div>
          </section>

          {(currentWarnings.length > 0 || result.documents.length > 0) && (
            <section className="catalog-generator-evidence">
              <div>
                <h2>Documentos processados</h2>
                {result.documents.length ? result.documents.map((document) => (
                  <p key={document.nome}><FileArchive size={15} /><strong>{document.nome}</strong><span>{document.tipo} · {document.status}</span></p>
                )) : <p>Nenhum anexo pôde ser carregado; os itens vieram da base estruturada.</p>}
              </div>
              <div>
                <h2>Avisos de validação</h2>
                {currentWarnings.length ? currentWarnings.map((warning) => <p key={warning}><AlertTriangle size={15} />{warning}</p>) : <p><Check size={15} />Nenhuma pendência automática encontrada.</p>}
              </div>
            </section>
          )}

          <section className="catalog-generator-review">
            <div className="catalog-generator-review-header">
              <div>
                <h2>Revisão dos requisitos e aderência</h2>
                <p>{currentCatalogMetrics.semModelo} sem modelo · {currentCatalogMetrics.divergencias} com divergência · {currentCatalogMetrics.reanalises} aguardando reanálise</p>
              </div>
              <button className="button button-primary" type="button" onClick={() => void runExport()} disabled={exporting || items.length === 0}>
                {exporting ? <LoaderCircle className="spin" size={17} /> : <Download size={17} />} Gerar catálogo e auditoria
              </button>
            </div>
            <div className="catalog-generator-table-wrap">
              <table className="catalog-generator-table">
                <thead><tr><th>Item</th><th>Produto e requisito</th><th>Unidade</th><th>Quantidade</th><th>Categoria</th><th>Modelo e aderência</th><th>Evidência</th></tr></thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td><input value={item.numero} onChange={(event) => updateItem(item.id, "numero", event.target.value)} />{item.lote && <small>Lote {item.lote}</small>}</td>
                      <td>
                        <input value={item.produto} aria-label={`Produto do item ${item.numero}`} onChange={(event) => updateItem(item.id, "produto", event.target.value)} />
                        <textarea value={item.descricao} aria-label={`Descrição do item ${item.numero}`} onChange={(event) => updateItem(item.id, "descricao", event.target.value)} />
                        <small title={item.fontes[0]?.url}>{item.fontes[0]?.documento} · {item.fontes[0]?.secao}</small>
                      </td>
                      <td><input value={item.unidade} aria-label={`Unidade do item ${item.numero}`} onChange={(event) => updateItem(item.id, "unidade", event.target.value)} /></td>
                      <td><input value={item.quantidade} aria-label={`Quantidade do item ${item.numero}`} onChange={(event) => updateItem(item.id, "quantidade", event.target.value)} /></td>
                      <td><input value={item.categoria} onChange={(event) => updateItem(item.id, "categoria", event.target.value)} /></td>
                      <td className="catalog-generator-fit">
                        {item.analise_desatualizada ? (
                          <><span className="evidence-status">reanálise necessária</span><small>Gere os arquivos para recalcular.</small></>
                        ) : item.modelo_referencia ? (
                          <>
                            <strong>{item.modelo_referencia.nome}</strong>
                            <span className={"evidence-status is-" + item.status_catalogo}>{humanizeCatalogStatus(item.analise_aderencia.resultado)}</span>
                            <small>Confiança {item.modelo_referencia.confianca} · {item.analise_aderencia.pendencias.length} pendência(s)</small>
                          </>
                        ) : (
                          <><span className="evidence-status is-bloqueado_sem_modelo">sem modelo correspondente</span><small>Características técnicas não serão publicadas.</small></>
                        )}
                      </td>
                      <td><span className={`evidence-status is-${item.status_evidencia}`}>{item.status_evidencia}</span>{item.campos_ausentes.length > 0 && <small>{item.campos_ausentes.join(", ")}</small>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="catalog-generator-observations" aria-label="Observações de repertório">
            <div className="catalog-generator-observations-heading">
              <Database size={18} aria-hidden="true" />
              <div>
                <h2>Observações de repertório</h2>
                <p>A conclusão considera cada componente técnico identificado no item.</p>
              </div>
            </div>
            <div className="catalog-generator-observation-list">
              {items.map((item) => {
                const observation = catalogObservation(item);
                const isEditing = editingRepertoireItemId === item.id;
                const canEditRepertoire = observation.status === "sem_repertorio" || Boolean(item.repertorio_usuario);
                return (
                  <article className={`catalog-generator-observation is-${observation.status}`} key={item.id}>
                    <header>
                      <span>Item {item.numero}{item.lote ? ` · Lote ${item.lote}` : ""}</span>
                      <strong>{observation.titulo}</strong>
                      <span className={`evidence-status is-${observation.status}`}>
                        {observation.status === "sem_repertorio" ? "1 · sem repertório" : observation.status === "evidencia_completa" ? "2 · evidência completa" : "3 · evidência parcial"}
                      </span>
                    </header>
                    <p>{observation.descricao}</p>
                    {observation.fonte && <small>Fonte: {observation.fonte}</small>}
                    {observation.evidencias.length > 0 && (
                      <div className="catalog-generator-observation-details is-supported">
                        <strong>Evidências localizadas</strong>
                        <ul>{observation.evidencias.map((entry) => <li key={entry}>{entry}</li>)}</ul>
                      </div>
                    )}
                    {observation.faltantes.length > 0 && (
                      <div className="catalog-generator-observation-details is-missing">
                        <strong>Dados faltantes ou divergentes</strong>
                        <ul>{observation.faltantes.map((entry) => <li key={entry}>{entry}</li>)}</ul>
                      </div>
                    )}
                    {canEditRepertoire && !isEditing && (
                      <button className="button button-secondary" type="button" onClick={() => openRepertoireEditor(item)}>
                        <SlidersHorizontal size={16} aria-hidden="true" />
                        {item.repertorio_usuario ? "Editar régua técnica" : "Cadastrar régua técnica"}
                      </button>
                    )}
                    {isEditing && (
                      <form className="catalog-generator-repertoire-form" onSubmit={(event) => { event.preventDefault(); void saveTechnicalRepertoire(item); }}>
                        <label>
                          Produto ou modelo Goldflex
                          <input value={repertoireProductName} maxLength={180} required onChange={(event) => setRepertoireProductName(event.target.value)} />
                        </label>
                        <div className="catalog-generator-parameter-list">
                          {technicalParameters.map((parameter, index) => (
                            <fieldset key={parameter.id}>
                              <legend>Parâmetro {index + 1}</legend>
                              <button
                                className="icon-button"
                                type="button"
                                title="Excluir parâmetro"
                                aria-label={`Excluir parâmetro ${index + 1}`}
                                disabled={technicalParameters.length === 1}
                                onClick={() => setTechnicalParameters((current) => current.filter((entry) => entry.id !== parameter.id))}
                              >
                                <Trash2 size={16} />
                              </button>
                              <label>
                                Componente ou peça
                                <input value={parameter.componente} maxLength={120} required placeholder="Ex.: Peça X" onChange={(event) => updateTechnicalParameter(parameter.id, "componente", event.target.value)} />
                              </label>
                              <label>
                                Característica avaliada
                                <input value={parameter.atributo} maxLength={120} required placeholder="Ex.: Tamanho" onChange={(event) => updateTechnicalParameter(parameter.id, "atributo", event.target.value)} />
                              </label>
                              <label>
                                Regra de comparação
                                <select value={parameter.comparacao} onChange={(event) => updateTechnicalParameter(parameter.id, "comparacao", event.target.value)}>
                                  <option value="intervalo">Faixa numérica</option>
                                  <option value="igual">Valor exato</option>
                                  <option value="contem">Característica contida</option>
                                </select>
                              </label>
                              {parameter.comparacao === "intervalo" ? (
                                <div className="catalog-generator-numeric-rule">
                                  <label>Exigido no item<input type="number" step="any" required value={parameter.valor_requerido} onChange={(event) => updateTechnicalParameter(parameter.id, "valor_requerido", event.target.value)} /></label>
                                  <label>Mínimo Goldflex<input type="number" step="any" required value={parameter.valor_minimo} onChange={(event) => updateTechnicalParameter(parameter.id, "valor_minimo", event.target.value)} /></label>
                                  <label>Máximo Goldflex<input type="number" step="any" required value={parameter.valor_maximo} onChange={(event) => updateTechnicalParameter(parameter.id, "valor_maximo", event.target.value)} /></label>
                                  <label>Unidade<input required maxLength={24} value={parameter.unidade} placeholder="cm" onChange={(event) => updateTechnicalParameter(parameter.id, "unidade", event.target.value)} /></label>
                                </div>
                              ) : (
                                <div className="catalog-generator-text-rule">
                                  <label>Exigido no item<input required maxLength={240} value={parameter.valor_requerido_texto} onChange={(event) => updateTechnicalParameter(parameter.id, "valor_requerido_texto", event.target.value)} /></label>
                                  <label>Atendido pela Goldflex<input required maxLength={240} value={parameter.valor_atendido_texto} onChange={(event) => updateTechnicalParameter(parameter.id, "valor_atendido_texto", event.target.value)} /></label>
                                </div>
                              )}
                              <label className="catalog-generator-parameter-evidence">
                                Evidência técnica
                                <textarea required maxLength={1000} value={parameter.evidencia} placeholder="Informe catálogo, laudo, ficha técnica ou validação do fabricante." onChange={(event) => updateTechnicalParameter(parameter.id, "evidencia", event.target.value)} />
                              </label>
                            </fieldset>
                          ))}
                        </div>
                        <button
                          className="button button-secondary"
                          type="button"
                          disabled={technicalParameters.length >= 30}
                          onClick={() => setTechnicalParameters((current) => [...current, newTechnicalParameter()])}
                        >
                          <Plus size={16} aria-hidden="true" /> Adicionar parâmetro
                        </button>
                        <label className="catalog-generator-coverage-check">
                          <input type="checkbox" checked={repertoireCoverageComplete} onChange={(event) => setRepertoireCoverageComplete(event.target.checked)} />
                          Esta régua contempla todos os componentes exigidos neste item.
                        </label>
                        <div className="catalog-generator-repertoire-actions">
                          <button className="button button-secondary" type="button" disabled={savingRepertoire} onClick={() => setEditingRepertoireItemId("")}>Cancelar</button>
                          <button className="button button-primary" type="submit" disabled={savingRepertoire}>
                            {savingRepertoire ? <LoaderCircle className="spin" size={16} /> : <Save size={16} />}
                            {savingRepertoire ? "Salvando..." : "Salvar e reavaliar"}
                          </button>
                        </div>
                      </form>
                    )}
                  </article>
                );
              })}
            </div>
          </section>

          {Object.keys(exports).length > 0 && (
            <section className="catalog-generator-exports">
              <strong>Arquivos prontos</strong>
              {Object.entries(exports).map(([kind, file]) => <a key={kind} href={file.download_url} download><Download size={16} />{catalogExportLabel(kind)}</a>)}
            </section>
          )}
        </>
      )}
    </section>
  );
}
