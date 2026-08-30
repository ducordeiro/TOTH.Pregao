import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Check, Download, ExternalLink, FileArchive, LoaderCircle, Play, ShieldCheck } from "lucide-react";
import { createCatalogGeneratorJob, exportGeneratedCatalog, getCatalogGeneratorJob } from "../api";
import type { CatalogExportFile, CatalogGeneratorJob, GeneratedCatalogItem } from "../types";

interface CatalogGeneratorBlockProps {
  pncpLink: string;
  onPncpLinkChange: (value: string) => void;
}

export function CatalogGeneratorBlock({ pncpLink, onPncpLinkChange }: CatalogGeneratorBlockProps) {
  const [job, setJob] = useState<CatalogGeneratorJob | null>(null);
  const [items, setItems] = useState<GeneratedCatalogItem[]>([]);
  const [exports, setExports] = useState<Record<string, CatalogExportFile>>({});
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    if (!job || !["queued", "processing"].includes(job.status)) return;
    const timer = window.setInterval(() => {
      getCatalogGeneratorJob(job.id)
        .then((updated) => {
          setJob(updated);
          if (updated.result) setItems(updated.result.items);
          if (updated.status === "failed") setError(updated.error);
        })
        .catch((reason) => setError(reason instanceof Error ? reason.message : "Falha ao acompanhar o processamento."));
    }, 900);
    return () => window.clearInterval(timer);
  }, [job?.id, job?.status]);

  const stageIndex = useMemo(
    () => Math.max(0, job?.stages.findIndex((stage) => stage.id === job.stage) ?? 0),
    [job],
  );

  const start = async () => {
    setError("");
    setExports({});
    setItems([]);
    try {
      setJob(await createCatalogGeneratorJob(pncpLink));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível iniciar o catálogo.");
    }
  };

  const updateItem = (id: string, field: keyof GeneratedCatalogItem, value: string) => {
    setItems((current) => current.map((item) => item.id === id ? { ...item, [field]: value } : item));
  };

  const runExport = async () => {
    if (!job) return;
    setExporting(true);
    setError("");
    try {
      const response = await exportGeneratedCatalog(job.id, items);
      setExports(response.exports);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Não foi possível exportar o catálogo.");
    } finally {
      setExporting(false);
    }
  };

  const result = job?.result;
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
          <button className="button button-primary" type="submit" disabled={job?.status === "processing" || job?.status === "queued"}>
            <Play size={17} aria-hidden="true" /> Processar edital
          </button>
        </div>
      </form>

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
            <div><span>Itens</span><strong>{items.length}</strong><small>{result.validation.incompletos} pendência(s)</small></div>
            <div><span>Fabricante</span><strong>Goldflex</strong><small>{result.manufacturer.cnpj}</small></div>
          </section>

          <section className="catalog-generator-object">
            <div><ShieldCheck size={18} /><strong>Objeto da contratação</strong></div>
            <p>{String(result.metadata.objeto || "Não informado pelo PNCP.")}</p>
            <a href={String(result.metadata.link_pncp)} target="_blank" rel="noreferrer">Abrir fonte oficial <ExternalLink size={14} /></a>
          </section>

          {(result.warnings.length > 0 || result.documents.length > 0) && (
            <section className="catalog-generator-evidence">
              <div>
                <h2>Documentos processados</h2>
                {result.documents.length ? result.documents.map((document) => (
                  <p key={document.nome}><FileArchive size={15} /><strong>{document.nome}</strong><span>{document.tipo} · {document.status}</span></p>
                )) : <p>Nenhum anexo pôde ser carregado; os itens vieram da base estruturada.</p>}
              </div>
              <div>
                <h2>Avisos de validação</h2>
                {result.warnings.length ? result.warnings.map((warning) => <p key={warning}><AlertTriangle size={15} />{warning}</p>) : <p><Check size={15} />Nenhuma pendência automática encontrada.</p>}
              </div>
            </section>
          )}

          <section className="catalog-generator-review">
            <div className="catalog-generator-review-header">
              <div><h2>Revisão dos itens</h2><p>Edite somente o que foi confirmado na documentação da licitação.</p></div>
              <button className="button button-primary" type="button" onClick={() => void runExport()} disabled={exporting || items.length === 0}>
                {exporting ? <LoaderCircle className="spin" size={17} /> : <Download size={17} />} Gerar arquivos
              </button>
            </div>
            <div className="catalog-generator-table-wrap">
              <table className="catalog-generator-table">
                <thead><tr><th>Item</th><th>Produto e descrição</th><th>Unidade</th><th>Quantidade</th><th>Categoria</th><th>Evidência</th></tr></thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id}>
                      <td><input value={item.numero} onChange={(event) => updateItem(item.id, "numero", event.target.value)} /></td>
                      <td>
                        <input value={item.produto} aria-label={`Produto do item ${item.numero}`} onChange={(event) => updateItem(item.id, "produto", event.target.value)} />
                        <textarea value={item.descricao} aria-label={`Descrição do item ${item.numero}`} onChange={(event) => updateItem(item.id, "descricao", event.target.value)} />
                        <small title={item.fontes[0]?.url}>{item.fontes[0]?.documento} · {item.fontes[0]?.secao}</small>
                      </td>
                      <td><input value={item.unidade} onChange={(event) => updateItem(item.id, "unidade", event.target.value)} /></td>
                      <td><input value={item.quantidade} onChange={(event) => updateItem(item.id, "quantidade", event.target.value)} /></td>
                      <td><input value={item.categoria} onChange={(event) => updateItem(item.id, "categoria", event.target.value)} /></td>
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
              {Object.entries(exports).map(([kind, file]) => <a key={kind} href={file.download_url} download><Download size={16} />{kind.toUpperCase()}</a>)}
            </section>
          )}
        </>
      )}
    </section>
  );
}
