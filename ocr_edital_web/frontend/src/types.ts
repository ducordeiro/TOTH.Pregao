export interface Template {
  id: string;
  name: string;
  display_name: string;
  size: number;
  updated_at: string;
  download_url: string;
}

export interface Responsible {
  id: string;
  nome_completo: string;
  empresa: string;
  cnpj: string;
  rg: string;
  cpf: string;
  observacoes: string;
  criado_em: string;
  atualizado_em: string;
}

export interface Bid {
  id?: string;
  score?: number;
  radar_status?: "new" | "triage" | "ignored" | "selected" | "converted_to_proposal";
  orgao: string;
  cnpj: string;
  ano: number;
  sequencial: number;
  numeroCompra: string;
  processo: string;
  modalidade?: string;
  objeto: string;
  uf: string;
  municipio: string;
  unidade?: string;
  codigoUnidade?: string;
  valorTotalEstimado?: number | string | null;
  modoDisputa?: string;
  situacao?: string;
  linkOrigem?: string;
  fonte?: string;
  publicacao?: string;
  abertura: string;
  encerramento: string;
  dataEncerramentoInformada?: boolean;
  itemCount?: number;
  itensIndexados?: boolean;
  link: string;
}

export interface ProposalItem {
  lote?: string;
  item: string;
  quantidade: string | null;
  unidade: string | null;
  categoria?: string;
  descricao: string;
  valor_unitario_estimado?: number | null;
  valor_total_estimado?: number | null;
  marca: string;
  valor_unitario: string;
  valor_total: string;
}

export type ProposalColumnKey =
  | "lote"
  | "item"
  | "quantidade"
  | "unidade"
  | "descricao"
  | "marca"
  | "valor_unitario"
  | "valor_total";

export type ProposalColumnWidths = Partial<Record<ProposalColumnKey, number>>;

export interface DescriptionReview {
  status: "ok" | "warn" | "error";
  message: string;
  complete_count: number;
  reviewed_count: number;
}

export interface PncpCheck {
  has_divergence: boolean;
  file_count: number;
  pncp_count: number;
  structured_count?: number;
  api_available?: boolean;
  api_error?: string;
  added_from_pncp?: string[];
  only_in_file?: string[];
  source?: string;
  file_error?: string;
}

export interface PncpInfo {
  cnpj: string;
  ano: number;
  sequencial: number;
  link: string;
  documento_tipo?: string;
  documento_usado?: string;
}

export interface IdentifyResponse {
  items: ProposalItem[];
  pncp?: PncpInfo;
  description_review?: DescriptionReview;
  pncp_items_check?: PncpCheck;
}

export interface CommercialTerms {
  prazo_entrega: string;
  prazo_pagamento: string;
  validade_proposta: string;
  fontes?: Partial<Record<
    "prazo_entrega" | "prazo_pagamento" | "validade_proposta",
    string
  >>;
  status?: "ok" | "warn";
  campos_nao_localizados?: string[];
}

export interface ProcessResponse extends IdentifyResponse {
  count: number;
  template_ref: string;
  template_name: string;
  template_source: "managed" | "upload";
  source_name: string;
  commercial_terms: CommercialTerms;
}

export type NodeType = "FIXED_TEXT" | "MINI_BOX";
export type MiniBoxTextAlign = "left" | "center" | "right" | "justify";

export interface BaseDocumentNode {
  id: string;
  type: NodeType;
  content: string;
}

export interface MiniBoxNode extends BaseDocumentNode {
  type: "MINI_BOX";
  order: number;
  text_align: MiniBoxTextAlign;
}

export interface FixedTextNode extends BaseDocumentNode {
  type: "FIXED_TEXT";
}

export type DocumentNode = MiniBoxNode | FixedTextNode;

export interface GeneratedTableBlock {
  id: string;
  type: "GENERATED_TABLE";
  content: string;
}

export interface DocxStructureResponse {
  document_signature: string;
  nodes: DocumentNode[];
  mini_box_count: number;
  generated_table_block: GeneratedTableBlock;
  warnings: string[];
}

export interface SearchResponse {
  results: Bid[];
  total?: number;
  source_total?: number;
  pagina?: number;
  tamanhoPagina?: number;
  total_pages?: number;
  has_previous?: boolean;
  has_next?: boolean;
  pages_checked?: number;
  source_pages?: number;
  complete?: boolean;
  searching?: boolean;
  source?: string;
  cache_hit?: boolean;
  rate_limited?: boolean;
  timed_out?: boolean;
  campoData?: "publicacao" | "abertura" | "encerramento";
  reconciliation?: {
    run_id?: string;
    status: "success" | "partial" | "failed";
    fetched: number;
    inserted: number;
    updated: number;
    skipped: number;
    failed: number;
    error?: string;
  } | null;
}

export interface OpportunityItem {
  numero: string;
  lote: string;
  descricao: string;
  quantidade: string;
  unidade: string;
  valor_unitario_estimado: number | string | null;
  valor_total_estimado: number | string | null;
  criterio_julgamento: string;
  situacao: string;
  tipo: string;
  granularity?: string;
  confidence?: number | string | null;
}

export interface OpportunityFile {
  titulo: string;
  tipo: string;
  url: string;
}

export interface OpportunityData {
  numero_compra: string;
  processo: string;
  modalidade: string;
  objeto: string;
  orgao: string;
  orgao_cnpj: string;
  unidade: string;
  codigo_unidade: string;
  municipio: string;
  uf: string;
  abertura: string;
  encerramento: string;
  situacao: string;
  valor_total_estimado: number | string | null;
  modo_disputa: string;
  link_pncp: string;
  link_origem: string;
  portal_origem: string;
  categorias: string[];
}

export interface OpportunityDetail {
  oportunidade: OpportunityData;
  arquivos: OpportunityFile[];
  itens: OpportunityItem[];
  verificacao_itens?: {
    has_divergence: boolean;
    file_count: number;
    pncp_count: number;
    only_in_file?: string[];
    added_from_pncp?: string[];
    file_error?: string;
    api_error?: string;
    source: "documento_oficial" | "api_pncp";
    documento?: string;
  };
  fontes: {
    oportunidade: string;
    arquivos: string;
    itens: string;
  };
  aviso_enriquecimento?: string;
}

export interface OpportunityAnswer {
  resposta: string;
  trechos: string[];
  documento: string;
  tipo_documento: string;
}

export interface GenerateResponse {
  download_url: string;
  filename: string;
}

export interface CatalogData {
  documento_licitacao: {
    titulo: string;
    numero_pregao: string;
    processo: string;
    modalidade: string;
    objeto: string;
    link_pncp: string;
  };
  orgao: {
    nome: string;
    unidade: string;
    cnpj: string;
    endereco: string;
    municipio: string;
    uf: string;
  };
  fabricante: {
    razao_social: string;
    nome_fantasia: string;
    cnpj: string;
    inscricao_estadual: string;
    endereco: string;
    telefone: string;
    email: string;
    site: string;
  };
  item: {
    numero: string;
    lote: string;
    quantidade: string;
    unidade: string;
    descricao: string;
  };
  produto: {
    marca: string;
    modelo: string;
    cor: string;
    revestimento: string;
    peso: string;
    garantia: string;
  };
  resumo: {
    caracteristicas: string;
  };
  secoes: {
    assento: string;
    encosto: string;
    estrutura: string;
    base: string;
    pes: string;
    bracos: string;
    rodizios: string;
    mecanismos: string;
    acessorios: string;
    dimensoes: string;
    normas: string;
    complementares: string;
    observacoes: string;
  };
  marca_dagua: {
    ativa: boolean;
    texto_personalizado: string;
    cor: string;
    opacidade: number;
  };
  origem: {
    tipo: string;
    arquivo: string;
    link: string;
  };
}

export type CatalogAssetRole = "logo" | "principal" | "secundaria" | "tecnica";

export interface CatalogAsset {
  id: string;
  file: File;
  role: CatalogAssetRole;
  section: string;
  caption: string;
  previewUrl: string;
}

export interface CatalogAlerts {
  errors: string[];
  warnings: string[];
}

export interface CatalogExportFile {
  filename: string;
  download_url: string;
}

export interface CatalogGenerateResponse {
  alerts: CatalogAlerts;
  exports: {
    docx: CatalogExportFile;
    pdf: CatalogExportFile;
    json: CatalogExportFile;
    images: CatalogExportFile;
  };
}

export interface CatalogDraftResponse {
  draft: CatalogData;
  items: ProposalItem[];
  source?: "documento_oficial" | "base_estruturada";
  enrichment_warning?: string;
  pncp?: PncpInfo & {
    metadata?: Record<string, string>;
  };
}

export interface GeneratedCatalogSource {
  documento: string;
  pagina: number | null;
  secao: string;
  url: string;
}

export interface GeneratedCatalogItem {
  id: string;
  numero: string;
  codigo: string;
  produto: string;
  descricao: string;
  especificacao_tecnica: string;
  unidade: string;
  quantidade: string;
  marca_referencia: string;
  valor_estimado: string | number;
  criterios_aceitacao: string;
  observacoes: string;
  categoria: string;
  subcategoria: string;
  status_evidencia: string;
  campos_ausentes: string[];
  conflitos: string[];
  fontes: GeneratedCatalogSource[];
}

export interface CatalogGeneratorResult {
  metadata: Record<string, string | number>;
  documents: Array<{ nome: string; tipo: string; status: string; origem: string }>;
  items: GeneratedCatalogItem[];
  validation: { incompletos: number; conflitos: number; avisos: string[] };
  warnings: string[];
  manufacturer: { razao_social: string; cnpj: string };
}

export interface CatalogGeneratorJob {
  id: string;
  pncp_link: string;
  status: "queued" | "processing" | "ready" | "failed";
  stage: string;
  progress: number;
  stages: Array<{ id: string; label: string }>;
  result: CatalogGeneratorResult | null;
  error: string;
}

export interface CatalogGeneratorExportResponse {
  exports: Record<string, CatalogExportFile>;
  validation: { incompletos: number; conflitos: number; avisos: string[] };
}

export type MessageKind = "info" | "success" | "warning" | "error";

export interface UiMessage {
  kind: MessageKind;
  text: string;
}

export type BusinessStage =
  | "oportunidade"
  | "qualificacao"
  | "disputa"
  | "classificacao"
  | "contrato";

export interface Business {
  id: string;
  contratacao_id: string;
  empresa: string;
  cnpj_orgao: string;
  ano: number;
  sequencial: number;
  link_pncp: string;
  titulo: string;
  titulo_oficial: string;
  orgao: string;
  municipio: string;
  uf: string;
  modalidade: string;
  numero_compra: string;
  processo: string;
  plataforma: string;
  fonte_integracao: string;
  abertura: string;
  encerramento: string;
  etapa: BusinessStage;
  situacao: string;
  prioridade: 1 | 2 | 3;
  favorito: boolean;
  arquivado: boolean;
  removido: boolean;
  responsavel: string;
  prazo_interno: string;
  anotacoes: string;
  decisao_comercial: string;
  checklist_concluido: number;
  checklist_total: number;
  total_itens: number;
  criado_em: string;
  atualizado_em: string;
  position_number: number | null;
  pode_mover: boolean;
}

export interface BusinessHistory {
  id: string;
  evento: string;
  etapa_anterior: string;
  etapa_nova: string;
  justificativa: string;
  criado_em: string;
}

export interface BusinessTask {
  id: string;
  titulo: string;
  concluida: boolean;
  ordem: number;
}

export interface BusinessFile {
  titulo: string;
  tipo: string;
  url: string;
  selecionado: boolean;
}

export interface BusinessItem {
  id: string;
  ordem: number;
  lote: string;
  numero: string;
  descricao: string;
  quantidade: string;
  unidade: string;
  valor_unitario_estimado: string;
  valor_total_estimado: string;
  criterio_julgamento: string;
  situacao: string;
}

export interface BusinessDetail extends Business {
  historico: BusinessHistory[];
  tarefas: BusinessTask[];
  arquivos: BusinessFile[];
  itens: BusinessItem[];
}


export interface KanbanColumn { id: string; name: string; position: number; color: string; created_at: string; updated_at: string; }
export type KanbanPriority = "critica" | "alta" | "normal" | "baixa";
export interface KanbanProposalInput {
  column_id: string; portal: string; position_number: string; modality: string; agency_name: string; notice_number: string;
  uasg: string; pncp_control_number: string; opening_at: string; critical_deadline: string;
  internal_identifier: string; title: string; object_description: string; phase_status: string;
  priority: KanbanPriority; pending_documents: string; estimated_value: string; responsible: string;
  next_review_at: string; notes: string; source_link: string;
}
export interface KanbanProposal extends KanbanProposalInput { id: string; created_at: string; updated_at: string; }
export interface KanbanBoard { columns: KanbanColumn[]; proposals: KanbanProposal[]; sync_status: "offline" | "pending" | "error" | "synced"; }
