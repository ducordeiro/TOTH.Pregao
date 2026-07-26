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
  BusinessDetail,
  BusinessStage,
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

export async function searchBids(params: URLSearchParams): Promise<SearchResponse> {
  const response = await fetch(`/pncp-search?${params.toString()}`);
  return parseJson<SearchResponse>(response);
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
): Promise<Business> {
  const response = await fetch("/api/negocios/importar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pncp_link: pncpLink, empresa }),
  });
  const payload = await parseJson<{ negocio: Business }>(response);
  return payload.negocio;
}

export type BusinessUpdate = Partial<Pick<
  Business,
  | "titulo"
  | "etapa"
  | "prioridade"
  | "favorito"
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
