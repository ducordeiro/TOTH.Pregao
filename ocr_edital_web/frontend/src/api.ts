import type {
  CatalogAsset,
  CatalogData,
  CatalogDraftResponse,
  CatalogGenerateResponse,
  CommercialTerms,
  GenerateResponse,
  IdentifyResponse,
  ProposalItem,
  ProcessResponse,
  Responsible,
  SearchResponse,
  Template,
  ProposalPreviewResponse,
  Business,
  KanbanBoard,
  KanbanProposalInput,
  BusinessDetail,
  BusinessStage,
  BusinessStageDefinition,
  Bid,
  OpportunityAnswer,
  OpportunityData,
  OpportunityDetail,
  OpportunityItem,
} from "./types";

interface ApiErrorPayload {
  error?: string;
}

async function parseJson<T>(response: Response): Promise<T> {
  const payload = (await response.json().catch(() => ({}))) as T & ApiErrorPayload;
  if (!response.ok) {
    throw new Error(payload.error || "Não foi possível concluir a operação.");
  }
  return payload;
}

export async function listTemplates(): Promise<Template[]> {
  const response = await fetch("/api/templates", {
    headers: { Accept: "application/json" },
  });
  const payload = await parseJson<{ templates: Template[] }>(response);
  return payload.templates;
}

export async function createTemplate(file: File): Promise<Template> {
  const body = new FormData();
  body.append("template_file", file);
  const response = await fetch("/api/templates", { method: "POST", body });
  const payload = await parseJson<{ template: Template }>(response);
  return payload.template;
}

export async function replaceTemplate(id: string, file: File): Promise<Template> {
  const body = new FormData();
  body.append("template_file", file);
  const response = await fetch(`/api/templates/${encodeURIComponent(id)}/replace`, {
    method: "POST",
    body,
  });
  const payload = await parseJson<{ template: Template }>(response);
  return payload.template;
}

export async function deleteTemplate(id: string): Promise<void> {
  const response = await fetch(`/api/templates/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  await parseJson<{ deleted: string }>(response);
}

export async function listResponsibles(): Promise<Responsible[]> {
  const response = await fetch("/api/responsaveis", {
    headers: { Accept: "application/json" },
  });
  const payload = await parseJson<{ responsaveis: Responsible[] }>(response);
  return payload.responsaveis;
}

export type ResponsiblePayload = Pick<
  Responsible,
  "nome_completo" | "empresa" | "cnpj" | "rg" | "cpf" | "observacoes"
>;

export async function createResponsible(data: ResponsiblePayload): Promise<Responsible> {
  const response = await fetch("/api/responsaveis", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const payload = await parseJson<{ responsavel: Responsible }>(response);
  return payload.responsavel;
}

export async function updateResponsible(
  id: string,
  data: ResponsiblePayload,
): Promise<Responsible> {
  const response = await fetch(`/api/responsaveis/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const payload = await parseJson<{ responsavel: Responsible }>(response);
  return payload.responsavel;
}

export async function deleteResponsible(id: string): Promise<void> {
  const response = await fetch(`/api/responsaveis/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  await parseJson<{ deleted: string }>(response);
}

export async function searchLocalBids(params: URLSearchParams): Promise<SearchResponse> {
  const response = await fetch(`/internal/opportunities?${params.toString()}`);
  return parseJson<SearchResponse>(response);
}

export async function searchOnlineBids(params: URLSearchParams): Promise<SearchResponse> {
  const response = await fetch(`/pncp-search?${params.toString()}`);
  return parseJson<SearchResponse>(response);
}

export async function searchBids(params: URLSearchParams): Promise<SearchResponse> {
  return searchLocalBids(params);
}

export interface EtlSyncResult {
  run_id?: string;
  status: string;
  total_fetched: number;
  total_inserted: number;
  total_updated: number;
  total_skipped: number;
  total_failed: number;
  dry_run?: boolean;
}

export async function syncPncpOpportunities(
  params: URLSearchParams,
): Promise<EtlSyncResult> {
  const response = await fetch("/internal/etl/pncp-sync", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      run_type: "manual",
      source_endpoint: "proposta",
      max_pages: 2,
      max_records: 100,
      fetch_details: false,
      dry_run: false,
      filters: Object.fromEntries(params.entries()),
    }),
  });
  return parseJson<EtlSyncResult>(response);
}

export async function getOpportunityDetail(bid: Bid): Promise<OpportunityDetail> {
  if (bid.id) {
    const response = await fetch(`/internal/opportunities/${encodeURIComponent(bid.id)}`);
    return parseJson<OpportunityDetail>(response);
  }
  const params = new URLSearchParams({
    pncp_link: bid.link,
    numero_compra: bid.numeroCompra,
    processo: bid.processo,
    modalidade: bid.modalidade || "",
    objeto: bid.objeto,
    orgao: bid.orgao,
    municipio: bid.municipio,
    uf: bid.uf,
    unidade: bid.unidade || "",
    codigo_unidade: bid.codigoUnidade || "",
    valor_total_estimado: String(bid.valorTotalEstimado ?? ""),
    modo_disputa: bid.modoDisputa || "",
    situacao: bid.situacao || "",
    link_sistema_origem: bid.linkOrigem || "",
    abertura: bid.abertura,
    encerramento: bid.encerramento,
  });
  const response = await fetch(`/api/oportunidades/detalhe?${params.toString()}`);
  return parseJson<OpportunityDetail>(response);
}

export async function convertOpportunityToBusiness(
  opportunityId: string,
  items: OpportunityItem[],
): Promise<Business> {
  const response = await fetch(
    `/internal/opportunities/${encodeURIComponent(opportunityId)}/convert-to-proposal`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ itens: items }),
    },
  );
  const payload = await parseJson<{ negocio: Business }>(response);
  return payload.negocio;
}

export async function askOpportunityDocument(
  pncpLink: string,
  question: string,
): Promise<OpportunityAnswer> {
  const response = await fetch("/api/oportunidades/conversar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pncp_link: pncpLink, pergunta: question }),
  });
  return parseJson<OpportunityAnswer>(response);
}

export async function identifyItems(
  pncpLink: string,
  signal?: AbortSignal,
): Promise<IdentifyResponse> {
  const params = new URLSearchParams({ pncp_link: pncpLink });
  const response = await fetch(`/identify-items?${params.toString()}`, { signal });
  return parseJson<IdentifyResponse>(response);
}

export async function getCatalogDraft(
  pncpLink: string,
  itemKey: string,
): Promise<CatalogDraftResponse> {
  const params = new URLSearchParams({
    pncp_link: pncpLink,
    item_key: itemKey,
  });
  const response = await fetch(`/catalog/draft?${params.toString()}`);
  return parseJson<CatalogDraftResponse>(response);
}

export async function generateCatalog(
  data: CatalogData,
  assets: CatalogAsset[],
): Promise<CatalogGenerateResponse> {
  const body = new FormData();
  const assetMetadata = assets.map((asset, index) => {
    const uploadKey = `asset_${index}`;
    body.append(uploadKey, asset.file, asset.file.name);
    return {
      upload_key: uploadKey,
      role: asset.role,
      section: asset.section,
      caption: asset.caption,
    };
  });
  body.append("data", JSON.stringify({ data, assets: assetMetadata }));
  const response = await fetch("/catalog/generate", { method: "POST", body });
  return parseJson<CatalogGenerateResponse>(response);
}

export async function processProposal(body: FormData): Promise<ProcessResponse> {
  const response = await fetch("/process", { method: "POST", body });
  return parseJson<ProcessResponse>(response);
}

export async function generateProposal(
  items: ProposalItem[],
  templateRef: string,
  sourceName: string,
  responsibleId: string,
  commercialTerms: CommercialTerms,
): Promise<GenerateResponse> {
  const response = await fetch("/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      items,
      template_ref: templateRef,
      source_name: sourceName,
      responsible_id: responsibleId,
      commercial_terms: commercialTerms,
    }),
  });
  return parseJson<GenerateResponse>(response);
}

export async function previewProposal(
  items: ProposalItem[],
  templateRef: string,
  sourceName: string,
  responsibleId: string,
  commercialTerms: CommercialTerms,
): Promise<ProposalPreviewResponse> {
  const response = await fetch("/proposal-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      items,
      template_ref: templateRef,
      source_name: sourceName,
      responsible_id: responsibleId,
      commercial_terms: commercialTerms,
    }),
  });
  return parseJson<ProposalPreviewResponse>(response);
}

export async function listBusinesses(includeArchived = false): Promise<Business[]> {
  const suffix = includeArchived ? "?arquivados=1" : "";
  const response = await fetch(`/api/negocios${suffix}`, {
    headers: { Accept: "application/json" },
  });
  const payload = await parseJson<{ negocios: Business[] }>(response);
  return payload.negocios;
}

export async function listBusinessStages(): Promise<BusinessStageDefinition[]> {
  const response = await fetch("/api/negocios/etapas", {
    headers: { Accept: "application/json" },
  });
  const payload = await parseJson<{ etapas: BusinessStageDefinition[] }>(response);
  return payload.etapas;
}

export async function createBusinessStage(label: string): Promise<BusinessStageDefinition[]> {
  const response = await fetch("/api/negocios/etapas", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label }),
  });
  const payload = await parseJson<{ etapas: BusinessStageDefinition[] }>(response);
  return payload.etapas;
}

export async function updateBusinessStage(
  id: string,
  update: Partial<Pick<BusinessStageDefinition, "label" | "description">>,
): Promise<BusinessStageDefinition[]> {
  const response = await fetch(`/api/negocios/etapas/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  const payload = await parseJson<{ etapas: BusinessStageDefinition[] }>(response);
  return payload.etapas;
}

export async function getBusiness(id: string): Promise<BusinessDetail> {
  const response = await fetch(`/api/negocios/${encodeURIComponent(id)}`, {
    headers: { Accept: "application/json" },
  });
  const payload = await parseJson<{ negocio: BusinessDetail }>(response);
  return payload.negocio;
}

export async function importBusiness(
  pncpLink: string,
  empresa: string,
  items?: OpportunityItem[],
  opportunity?: OpportunityData,
): Promise<Business> {
  const response = await fetch("/api/negocios/importar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      pncp_link: pncpLink,
      empresa,
      ...(items !== undefined ? { itens: items } : {}),
      ...(opportunity ? { oportunidade: opportunity } : {}),
    }),
  });
  const payload = await parseJson<{ negocio: Business }>(response);
  return payload.negocio;
}

export type BusinessUpdate = Partial<Pick<
  Business,
  | "titulo"
  | "etapa"
  | "prioridade"
  | "position_number"
  | "favorito"
  | "abertura"
  | "responsavel"
  | "prazo_interno"
  | "anotacoes"
  | "decisao_comercial"
  | "arquivado"
  | "removido"
>> & {
  titulo_interno?: string;
  justificativa?: string;
};

export async function updateBusiness(
  id: string,
  update: BusinessUpdate,
): Promise<Business> {
  const response = await fetch(`/api/negocios/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(update),
  });
  const payload = await parseJson<{ negocio: Business }>(response);
  return payload.negocio;
}

export async function moveBusiness(
  id: string,
  etapa: BusinessStage,
  justificativa = "",
): Promise<Business> {
  return updateBusiness(id, { etapa, justificativa });
}

export async function addBusinessTask(
  businessId: string,
  titulo: string,
): Promise<BusinessDetail> {
  const response = await fetch(
    `/api/negocios/${encodeURIComponent(businessId)}/tarefas`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo }),
    },
  );
  await parseJson(response);
  return getBusiness(businessId);
}

export async function updateBusinessTask(
  businessId: string,
  taskId: string,
  concluida: boolean,
): Promise<BusinessDetail> {
  const response = await fetch(
    `/api/negocios/${encodeURIComponent(businessId)}/tarefas/${encodeURIComponent(taskId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ concluida }),
    },
  );
  const payload = await parseJson<{ negocio: BusinessDetail }>(response);
  return payload.negocio;
}


export async function getKanbanBoard(): Promise<KanbanBoard> {
  return parseJson<KanbanBoard>(await fetch("/api/kanban", { headers: { Accept: "application/json" } }));
}
export async function createKanbanColumn(name: string) {
  return parseJson(await fetch("/api/kanban/columns", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }));
}
export async function updateKanbanColumn(id: string, update: { name?: string; direction?: "left" | "right" }) {
  return parseJson(await fetch(`/api/kanban/columns/${encodeURIComponent(id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) }));
}
export async function moveKanbanColumn(id: string, direction: "left" | "right") { return updateKanbanColumn(id, { direction }); }
export async function deleteKanbanColumn(id: string) {
  return parseJson(await fetch(`/api/kanban/columns/${encodeURIComponent(id)}`, { method: "DELETE" }));
}
export async function saveKanbanProposal(input: KanbanProposalInput, id?: string) {
  const url = id ? `/api/kanban/proposals/${encodeURIComponent(id)}` : "/api/kanban/proposals";
  return parseJson(await fetch(url, { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(input) }));
}
export async function moveKanbanProposal(id: string, columnId: string) {
  return parseJson(await fetch(`/api/kanban/proposals/${encodeURIComponent(id)}/move`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ column_id: columnId }) }));
}
export async function deleteKanbanProposal(id: string) {
  return parseJson(await fetch(`/api/kanban/proposals/${encodeURIComponent(id)}`, { method: "DELETE" }));
}
