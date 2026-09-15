import { memo } from "react";
import { SlidersHorizontal } from "lucide-react";
import type { CatalogEvidenceObservation, GeneratedCatalogItem } from "../types";

export const catalogObservation = (item: GeneratedCatalogItem): CatalogEvidenceObservation => (
  item.observacao_repertorio || {
    status: item.modelo_referencia ? "evidencia_parcial" : "sem_repertorio",
    titulo: item.modelo_referencia ? "Foram encontradas evidências parciais" : "Não foi encontrado repertório para o item",
    descricao: item.modelo_referencia
      ? "Esta análise foi criada antes da auditoria por componentes e precisa ser reavaliada."
      : "Não há dados técnicos cadastrados que permitam validar os componentes solicitados.",
    evidencias: [],
    faltantes: item.analise_aderencia?.pendencias || ["Cadastre os parâmetros técnicos do item."],
    fonte: item.modelo_referencia?.fonte || "",
  }
);

export const CatalogItemRow = memo(function CatalogItemRow({ item, disabled, onChange }: {
  item: GeneratedCatalogItem;
  disabled: boolean;
  onChange: (id: string, field: keyof GeneratedCatalogItem, value: string) => void;
}) {
  return <tr>
    <td><input disabled={disabled} aria-label={`Número do item ${item.numero}`} value={item.numero} onChange={(event) => onChange(item.id, "numero", event.target.value)} />{item.lote && <small>Lote {item.lote}</small>}</td>
    <td>
      <input disabled={disabled} value={item.produto} aria-label={`Produto do item ${item.numero}`} onChange={(event) => onChange(item.id, "produto", event.target.value)} />
      <textarea disabled={disabled} value={item.descricao} aria-label={`Descrição do item ${item.numero}`} onChange={(event) => onChange(item.id, "descricao", event.target.value)} />
      <small title={item.fontes[0]?.url}>{item.fontes[0]?.documento} · {item.fontes[0]?.secao}</small>
    </td>
    <td><input disabled={disabled} value={item.unidade} aria-label={`Unidade do item ${item.numero}`} onChange={(event) => onChange(item.id, "unidade", event.target.value)} /></td>
    <td><input disabled={disabled} value={item.quantidade} aria-label={`Quantidade do item ${item.numero}`} onChange={(event) => onChange(item.id, "quantidade", event.target.value)} /></td>
    <td><input disabled={disabled} aria-label={`Categoria do item ${item.numero}`} value={item.categoria} onChange={(event) => onChange(item.id, "categoria", event.target.value)} /></td>
    <td className="catalog-generator-fit">
      {item.analise_desatualizada ? <><span className="evidence-status">reanálise necessária</span><small>Gere os arquivos para recalcular.</small></>
        : item.modelo_referencia ? <>
          <strong>{item.modelo_referencia.nome}</strong>
          <span className={"evidence-status is-" + item.status_catalogo}>{item.analise_aderencia.resultado.replaceAll("_", " ")}</span>
          <small>Confiança {item.modelo_referencia.confianca} · {item.analise_aderencia.pendencias.length} pendência(s)</small>
        </> : <><span className="evidence-status is-bloqueado_sem_modelo">sem modelo correspondente</span><small>Características técnicas não serão publicadas.</small></>}
    </td>
    <td><span className={`evidence-status is-${item.status_evidencia}`}>{item.status_evidencia}</span>{item.campos_ausentes.length > 0 && <small>{item.campos_ausentes.join(", ")}</small>}</td>
  </tr>;
});

export const CatalogObservationContent = memo(function CatalogObservationContent({ item, isEditing, disabled, onEdit }: {
  item: GeneratedCatalogItem;
  isEditing: boolean;
  disabled: boolean;
  onEdit: (item: GeneratedCatalogItem) => void;
}) {
  const observation = catalogObservation(item);
  const pending = [...new Set([...observation.faltantes, ...item.analise_aderencia.pendencias, ...(item.perguntas_pendentes || []).map((question) => question.requisito)])];
  const canEdit = pending.length > 0 || observation.status === "sem_repertorio" || Boolean(item.repertorio_usuario);
  return <>
    <header>
      <span>Item {item.numero}{item.lote ? ` · Lote ${item.lote}` : ""}</span>
      <strong>{observation.titulo}</strong>
      <span className={`evidence-status is-${observation.status}`}>
        {observation.status === "sem_repertorio" ? "1 · sem repertório" : observation.status === "evidencia_completa" ? "2 · evidência completa" : "3 · evidência parcial"}
      </span>
    </header>
    <p>{observation.descricao}</p>
    {observation.fonte && <small>Fonte: {observation.fonte}</small>}
    {!item.analise_desatualizada && Boolean(item.referencias_complementares?.length) && <details className="catalog-generator-observation-details">
      <summary>Referências complementares para revisão ({item.referencias_complementares?.length})</summary>
      <ul>{item.referencias_complementares?.map((reference) => <li key={reference.id}>
        <strong>{reference.fonte}</strong>
        {(reference.pagina || reference.secao) && <small>{reference.pagina ? `Página ${reference.pagina}` : reference.secao}</small>}
        <p>{reference.trecho}</p><small>{reference.nota}</small>
      </li>)}</ul>
    </details>}
    {observation.evidencias.length > 0 && <div className="catalog-generator-observation-details is-supported">
      <strong>Evidências localizadas</strong><ul>{observation.evidencias.map((entry) => <li key={entry}>{entry}</li>)}</ul>
    </div>}
    {pending.length > 0 && <div className="catalog-generator-observation-details is-missing">
      <strong>Dados faltantes ou divergentes</strong><ul>{pending.map((entry) => <li key={entry}>{entry}</li>)}</ul>
    </div>}
    {canEdit && !isEditing && <button className="button button-secondary" type="button" disabled={disabled || item.analise_desatualizada} onClick={() => onEdit(item)}>
      <SlidersHorizontal size={16} aria-hidden="true" />{pending.length ? "Responder pendências" : "Editar régua técnica"}
    </button>}
  </>;
});
