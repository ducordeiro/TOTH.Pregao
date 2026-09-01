import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, BookOpenCheck, Check, Download, ExternalLink, FileArchive, LoaderCircle, Play, Scale } from "lucide-react";
import { createCatalogGeneratorJob, exportGeneratedCatalog, getCatalogGeneratorJob } from "../api";
import type { CatalogExportFile, CatalogGeneratorJob, GeneratedCatalogItem, OpportunityItemSelection } from "../types";
import { opportunityItemKey, selectionForLink } from "../opportunitySelection";

interface CatalogGeneratorBlockProps {
  pncpLink: string;
  onPncpLinkChange: (value: string) => void;
  itemSelection?: OpportunityItemSelection | null;
}

const humanizeCatalogStatus = (value: string) => value.replaceAll("_", " ");

const catalogExportLabel = (kind: string) => {
  if (kind === "docx") return "Catálogo DOCX";
  if (kind === "pdf") return "Catálogo PDF";
  return "Auditoria " + kind.toUpperCase();
};

export function CatalogGeneratorBlock({ pncpLink, onPncpLinkChange, itemSelection }: CatalogGeneratorBlockProps) {
  const [job, setJob] = useState<CatalogGeneratorJob | null>(null);
  const [items, setItems] = useState<GeneratedCatalogItem[]>([]);
  const [exports, setExports] = useState<Record<string, CatalogExportFile>>({});
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const [starting, setStarting] = useState(false);
  const requestVersion = useRef(0);
  const exportVersion = useRef(0);
  const selection = selectionForLink(itemSelection, pncpLink);

  useEffect(() => {
    requestVersion.current += 1;
    exportVersion.current += 1;
    setJob(null);
    setItems([]);
    setExports({});
    setError("");
    setStarting(false);
    setExporting(false);
  }, [pncpLink, itemSelection]);

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

          <section className="catalog-generator-policy" aria-label="Padrão técnico do catálogo">
            <div className="catalog-generator-policy-heading">
              <BookOpenCheck size={19} />
              <div><h2>Padrão técnico Goldflex</h2><p>Catálogo editorial e auditoria da oportunidade são documentos independentes.</p></div>
            </div>
            <div className="catalog-generator-policy-grid">
              <div><span>Formato</span><strong>{result.catalog_policy.page_size} vertical</strong></div>
              <div><span>Publicação</span><strong>Somente dados evidenciados</strong></div>
              <div><span>Base analisada</span><strong>{result.repertoire.source_documents} documentos</strong></div>
              <div><span>Liberação</span><strong>Revisão humana obrigatória</strong></div>
            </div>
            <p className="catalog-generator-policy-note">{result.repertoire.scope_note}</p>
          </section>

          <section className="catalog-generator-object">
            <div><Scale size={18} /><strong>Objeto usado somente na auditoria de aderência</strong></div>
            <p>{String(result.metadata.objeto || "Não informado pelo PNCP.")}</p>
            <a href={String(result.metadata.link_pncp)} target="_blank" rel="noreferrer">Abrir fonte oficial <ExternalLink size={14} /></a>
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
