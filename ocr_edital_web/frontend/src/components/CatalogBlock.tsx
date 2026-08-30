import { useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Download,
  Eye,
  FileArchive,
  FileJson,
  FileText,
  ImagePlus,
  LoaderCircle,
  Search,
  Trash2,
  Upload,
} from "lucide-react";
import { generateCatalog, getCatalogDraft, identifyItems } from "../api";
import type {
  CatalogAlerts,
  CatalogAsset,
  CatalogAssetRole,
  CatalogData,
  CatalogGenerateResponse,
  ProposalItem,
  UiMessage,
} from "../types";
import { itemKey, normalizePncpUrl } from "../utils";
import { CatalogPreview, TECHNICAL_SECTION_OPTIONS } from "./CatalogPreview";
import { StatusMessage } from "./StatusMessage";

type CatalogTab = "cadastro" | "preview" | "alertas";

const EMPTY_CATALOG: CatalogData = {
  documento_licitacao: {
    titulo: "CATÁLOGO TÉCNICO",
    numero_pregao: "",
    processo: "",
    modalidade: "",
    objeto: "",
    link_pncp: "",
  },
  orgao: {
    nome: "",
    unidade: "",
    cnpj: "",
    endereco: "",
    municipio: "",
    uf: "",
  },
  fabricante: {
    razao_social: "",
    nome_fantasia: "",
    cnpj: "",
    inscricao_estadual: "",
    endereco: "",
    telefone: "",
    email: "",
    site: "",
  },
  item: {
    numero: "",
    lote: "",
    quantidade: "",
    unidade: "UND",
    descricao: "",
  },
  produto: {
    marca: "",
    modelo: "",
    cor: "",
    revestimento: "",
    peso: "",
    garantia: "",
  },
  resumo: { caracteristicas: "" },
  secoes: {
    assento: "",
    encosto: "",
    estrutura: "",
    base: "",
    pes: "",
    bracos: "",
    rodizios: "",
    mecanismos: "",
    acessorios: "",
    dimensoes: "",
    normas: "",
    complementares: "",
    observacoes: "",
  },
  marca_dagua: {
    ativa: true,
    texto_personalizado: "",
    cor: "#C62828",
    opacidade: 12,
  },
  origem: {
    tipo: "",
    arquivo: "",
    link: "",
  },
};

function hasValues(group: Record<string, unknown>): boolean {
  return Object.values(group).some((value) => String(value || "").trim());
}

function clientAlerts(data: CatalogData, assets: CatalogAsset[]): CatalogAlerts {
  const errors: string[] = [];
  const warnings: string[] = [];
  const required: Array<[string, string]> = [
    [data.documento_licitacao.numero_pregao, "Número do pregão"],
    [data.documento_licitacao.processo, "Processo"],
    [data.orgao.nome, "Órgão destinatário"],
    [data.fabricante.razao_social, "Razão social do fabricante"],
    [data.fabricante.cnpj, "CNPJ do fabricante"],
    [data.item.numero, "Número do item"],
    [data.item.descricao, "Descrição do item"],
    [data.produto.marca, "Marca"],
    [data.produto.modelo, "Modelo"],
  ];
  required.forEach(([value, label]) => {
    if (!value.trim()) errors.push(`Campo ausente: ${label}.`);
  });
  const cnpj = data.fabricante.cnpj.replace(/\D/g, "");
  if (cnpj && cnpj.length !== 14) errors.push("O CNPJ do fabricante deve possuir 14 dígitos.");
  if (!assets.some((asset) => asset.role === "logo")) {
    warnings.push("Logo da empresa não informado.");
  }
  if (!assets.some((asset) => asset.role === "principal")) {
    errors.push("Imagem principal do produto não informada.");
  }
  const technicalText = Object.values(data.secoes).join(" ").toLocaleLowerCase("pt-BR");
  [
    ["com braços", "sem braços"],
    ["com rodízios", "sem rodízios"],
    ["base fixa", "base giratória"],
  ].forEach(([left, right]) => {
    if (technicalText.includes(left) && technicalText.includes(right)) {
      warnings.push(`Possível informação contraditória: “${left}” e “${right}”.`);
    }
  });
  const units = new Set(
    [...data.secoes.dimensoes.matchAll(/\b(mm|cm|m)\b/gi)].map(
      (match) => match[1].toLocaleLowerCase("pt-BR"),
    ),
  );
  if (units.size > 1) {
    warnings.push("A seção DIMENSÕES utiliza unidades de comprimento diferentes.");
  }
  const emptySections = TECHNICAL_SECTION_OPTIONS
    .filter((section) => !data.secoes[section.key].trim())
    .map((section) => section.label);
  if (emptySections.length) {
    warnings.push(`Seções vazias não serão exportadas: ${emptySections.join(", ")}.`);
  }
  return { errors, warnings };
}

function Field({
  label,
  children,
  wide = false,
}: {
  label: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <label className={wide ? "catalog-field is-wide" : "catalog-field"}>
      <span>{label}</span>
      {children}
    </label>
  );
}

interface CatalogBlockProps {
  pncpLink: string;
  onPncpLinkChange: (link: string) => void;
}

export function CatalogBlock({ pncpLink, onPncpLinkChange }: CatalogBlockProps) {
  const [tab, setTab] = useState<CatalogTab>("cadastro");
  const [data, setData] = useState<CatalogData>(EMPTY_CATALOG);
  const [items, setItems] = useState<ProposalItem[]>([]);
  const [selectedItemKey, setSelectedItemKey] = useState("");
  const [assets, setAssets] = useState<CatalogAsset[]>([]);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exports, setExports] = useState<CatalogGenerateResponse["exports"] | null>(null);
  const alertsPanelRef = useRef<HTMLDivElement>(null);
  const alerts = useMemo(() => clientAlerts(data, assets), [assets, data]);

  const updateGroup = <
    Group extends keyof CatalogData,
    FieldName extends keyof CatalogData[Group],
  >(
    group: Group,
    field: FieldName,
    value: CatalogData[Group][FieldName],
  ) => {
    setData((current) => ({
      ...current,
      [group]: {
        ...current[group],
        [field]: value,
      },
    }));
    setExports(null);
  };

  const applyDraft = async (link: string, key: string) => {
    const response = await getCatalogDraft(link, key);
    setData((current) => ({
      ...response.draft,
      fabricante: hasValues(current.fabricante)
        ? current.fabricante
        : response.draft.fabricante,
      produto: {
        ...response.draft.produto,
        marca: current.produto.marca || response.draft.produto.marca,
        modelo: current.produto.modelo || response.draft.produto.modelo,
        cor: current.produto.cor || response.draft.produto.cor,
        revestimento: current.produto.revestimento || response.draft.produto.revestimento,
        peso: current.produto.peso || response.draft.produto.peso,
        garantia: current.produto.garantia || response.draft.produto.garantia,
      },
      marca_dagua: current.marca_dagua,
    }));
    setMessage({
      kind: response.enrichment_warning ? "warning" : "success",
      text: response.source === "base_estruturada"
        ? `Item ${response.draft.item.numero} estruturado a partir da base local. O documento oficial não estava disponível para enriquecimento.`
        : `Item ${response.draft.item.numero} estruturado a partir do arquivo oficial do edital.`,
    });
    setExports(null);
  };

  const loadEdict = async () => {
    if (busy) return;
    const normalized = normalizePncpUrl(pncpLink);
    if (!normalized) {
      setMessage({ kind: "warning", text: "Informe um link válido de edital do PNCP." });
      return;
    }
    setBusy(true);
    setMessage({ kind: "info", text: "Lendo o arquivo oficial do edital..." });
    try {
      onPncpLinkChange(normalized);
      const identification = await identifyItems(normalized);
      const first = identification.items[0];
      if (!first) throw new Error("Nenhum item foi encontrado no arquivo oficial.");
      const firstKey = itemKey(first);
      setItems(identification.items);
      setSelectedItemKey(firstKey);
      await applyDraft(normalized, firstKey);
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível ler o edital.",
      });
    } finally {
      setBusy(false);
    }
  };

  const selectItem = async (key: string) => {
    setSelectedItemKey(key);
    const normalized = normalizePncpUrl(pncpLink);
    if (!normalized || !key) return;
    setBusy(true);
    setMessage({ kind: "info", text: "Estruturando os dados do item selecionado..." });
    try {
      await applyDraft(normalized, key);
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível estruturar o item.",
      });
    } finally {
      setBusy(false);
    }
  };

  const addAsset = (file: File, role: CatalogAssetRole) => {
    const asset: CatalogAsset = {
      id: crypto.randomUUID(),
      file,
      role,
      section: role === "tecnica" ? "assento" : "",
      caption: "",
      previewUrl: URL.createObjectURL(file),
    };
    setAssets((current) => {
      if (role === "logo") {
        current.filter((item) => item.role === "logo")
          .forEach((item) => URL.revokeObjectURL(item.previewUrl));
        return [...current.filter((item) => item.role !== "logo"), asset];
      }
      if (role === "principal") {
        return [
          ...current.map((item) =>
            item.role === "principal" ? { ...item, role: "secundaria" as const } : item,
          ),
          asset,
        ];
      }
      return [...current, asset];
    });
    setExports(null);
  };

  const addProductImages = (files: FileList | null) => {
    if (!files) return;
    const hasMain = assets.some((asset) => asset.role === "principal");
    Array.from(files).forEach((file, index) => {
      addAsset(file, !hasMain && index === 0 ? "principal" : "secundaria");
    });
  };

  const updateAsset = (
    id: string,
    field: "role" | "section" | "caption",
    value: string,
  ) => {
    setAssets((current) =>
      current.map((asset) => {
        if (asset.id !== id) {
          if (field === "role" && value === "principal" && asset.role === "principal") {
            return { ...asset, role: "secundaria" };
          }
          return asset;
        }
        return {
          ...asset,
          [field]: value,
          section:
            field === "role" && value !== "tecnica"
              ? ""
              : field === "role" && value === "tecnica" && !asset.section
                ? "assento"
                : asset.section,
        } as CatalogAsset;
      }),
    );
    setExports(null);
  };

  const removeAsset = (id: string) => {
    setAssets((current) => {
      const removed = current.find((asset) => asset.id === id);
      if (removed) URL.revokeObjectURL(removed.previewUrl);
      return current.filter((asset) => asset.id !== id);
    });
    setExports(null);
  };

  const exportCatalog = async () => {
    if (generating) return;
    if (alerts.errors.length) {
      setTab("alertas");
      setMessage({
        kind: "warning",
        text: `${alerts.errors.length} pendência(s) obrigatória(s) impedem a geração do catálogo.`,
      });
      window.requestAnimationFrame(() => {
        alertsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      return;
    }
    setGenerating(true);
    setMessage({ kind: "info", text: "Gerando Word, PDF, JSON e pacote de imagens..." });
    try {
      const response = await generateCatalog(data, assets);
      setExports(response.exports);
      setMessage({ kind: "success", text: "Catálogo técnico gerado com sucesso." });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível gerar o catálogo.",
      });
    } finally {
      setGenerating(false);
    }
  };

  return (
    <section className="workspace-section catalog-workspace" aria-labelledby="catalog-heading">
      <div className="section-heading catalog-heading">
        <div>
          <span className="eyebrow">Bloco 3</span>
          <h2 id="catalog-heading">Catálogo técnico</h2>
          <p>Dados estruturados do item e documentos técnicos para a licitação.</p>
        </div>
        <div className="catalog-tab-list" role="tablist" aria-label="Visualização do catálogo">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "cadastro"}
            className={tab === "cadastro" ? "is-active" : ""}
            onClick={() => setTab("cadastro")}
          >
            <BookOpen size={16} />
            Cadastro
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "preview"}
            className={tab === "preview" ? "is-active" : ""}
            onClick={() => setTab("preview")}
          >
            <Eye size={16} />
            Pré-visualização
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "alertas"}
            className={tab === "alertas" ? "is-active" : ""}
            onClick={() => setTab("alertas")}
          >
            <AlertTriangle size={16} />
            Alertas
            {(alerts.errors.length + alerts.warnings.length) > 0 && (
              <span className="catalog-alert-count">
                {alerts.errors.length + alerts.warnings.length}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="catalog-source-bar">
        <Field label="Link do edital no PNCP" wide>
          <input
            type="text"
            inputMode="url"
            value={pncpLink}
            placeholder="https://pncp.gov.br/app/editais/CNPJ/ANO/SEQUENCIAL"
            onChange={(event) => onPncpLinkChange(event.target.value)}
          />
        </Field>
        <button className="button button-primary" type="button" disabled={busy} onClick={loadEdict}>
          {busy ? <LoaderCircle className="is-spinning" size={17} /> : <Search size={17} />}
          {busy ? "Lendo edital..." : "Ler edital"}
        </button>
        <Field label="Item do edital">
          <select
            value={selectedItemKey}
            disabled={!items.length || busy}
            onChange={(event) => selectItem(event.target.value)}
          >
            {!items.length && <option value="">Nenhum item carregado</option>}
            {items.map((item) => (
              <option value={itemKey(item)} key={itemKey(item)}>
                Item {item.item} · {item.categoria || item.descricao.slice(0, 55)}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <StatusMessage message={message} />

      {tab === "cadastro" && (
        <div className="catalog-form">
          <details open>
            <summary><span>01</span> Dados do documento e da licitação</summary>
            <div className="catalog-field-grid">
              <Field label="Título"><input value={data.documento_licitacao.titulo} onChange={(event) => updateGroup("documento_licitacao", "titulo", event.target.value)} /></Field>
              <Field label="Número do pregão"><input value={data.documento_licitacao.numero_pregao} onChange={(event) => updateGroup("documento_licitacao", "numero_pregao", event.target.value)} /></Field>
              <Field label="Processo"><input value={data.documento_licitacao.processo} onChange={(event) => updateGroup("documento_licitacao", "processo", event.target.value)} /></Field>
              <Field label="Modalidade"><input value={data.documento_licitacao.modalidade} onChange={(event) => updateGroup("documento_licitacao", "modalidade", event.target.value)} /></Field>
              <Field label="Objeto" wide><textarea rows={3} value={data.documento_licitacao.objeto} onChange={(event) => updateGroup("documento_licitacao", "objeto", event.target.value)} /></Field>
            </div>
          </details>

          <details>
            <summary><span>02</span> Dados do órgão destinatário</summary>
            <div className="catalog-field-grid">
              <Field label="Órgão"><input value={data.orgao.nome} onChange={(event) => updateGroup("orgao", "nome", event.target.value)} /></Field>
              <Field label="Unidade"><input value={data.orgao.unidade} onChange={(event) => updateGroup("orgao", "unidade", event.target.value)} /></Field>
              <Field label="CNPJ"><input value={data.orgao.cnpj} onChange={(event) => updateGroup("orgao", "cnpj", event.target.value)} /></Field>
              <Field label="Município"><input value={data.orgao.municipio} onChange={(event) => updateGroup("orgao", "municipio", event.target.value)} /></Field>
              <Field label="UF"><input maxLength={2} value={data.orgao.uf} onChange={(event) => updateGroup("orgao", "uf", event.target.value.toUpperCase())} /></Field>
              <Field label="Endereço" wide><input value={data.orgao.endereco} onChange={(event) => updateGroup("orgao", "endereco", event.target.value)} /></Field>
            </div>
          </details>

          <details open>
            <summary><span>03</span> Dados cadastrais do fabricante</summary>
            <div className="catalog-field-grid">
              <Field label="Razão social"><input value={data.fabricante.razao_social} onChange={(event) => updateGroup("fabricante", "razao_social", event.target.value)} /></Field>
              <Field label="Nome fantasia"><input value={data.fabricante.nome_fantasia} onChange={(event) => updateGroup("fabricante", "nome_fantasia", event.target.value)} /></Field>
              <Field label="CNPJ"><input value={data.fabricante.cnpj} onChange={(event) => updateGroup("fabricante", "cnpj", event.target.value)} /></Field>
              <Field label="Inscrição estadual"><input value={data.fabricante.inscricao_estadual} onChange={(event) => updateGroup("fabricante", "inscricao_estadual", event.target.value)} /></Field>
              <Field label="Telefone"><input value={data.fabricante.telefone} onChange={(event) => updateGroup("fabricante", "telefone", event.target.value)} /></Field>
              <Field label="E-mail"><input type="email" value={data.fabricante.email} onChange={(event) => updateGroup("fabricante", "email", event.target.value)} /></Field>
              <Field label="Site"><input value={data.fabricante.site} onChange={(event) => updateGroup("fabricante", "site", event.target.value)} /></Field>
              <Field label="Endereço" wide><input value={data.fabricante.endereco} onChange={(event) => updateGroup("fabricante", "endereco", event.target.value)} /></Field>
            </div>
          </details>

          <details open>
            <summary><span>04</span> Dados do item</summary>
            <div className="catalog-field-grid">
              <Field label="Item"><input value={data.item.numero} onChange={(event) => updateGroup("item", "numero", event.target.value)} /></Field>
              <Field label="Lote"><input value={data.item.lote} onChange={(event) => updateGroup("item", "lote", event.target.value)} /></Field>
              <Field label="Quantidade"><input value={data.item.quantidade} onChange={(event) => updateGroup("item", "quantidade", event.target.value)} /></Field>
              <Field label="Unidade"><input value={data.item.unidade} onChange={(event) => updateGroup("item", "unidade", event.target.value)} /></Field>
              <Field label="Descrição do edital" wide><textarea rows={7} value={data.item.descricao} onChange={(event) => updateGroup("item", "descricao", event.target.value)} /></Field>
            </div>
          </details>

          <details open>
            <summary><span>05</span> Marca e modelo</summary>
            <div className="catalog-field-grid">
              <Field label="Marca"><input value={data.produto.marca} onChange={(event) => updateGroup("produto", "marca", event.target.value)} /></Field>
              <Field label="Modelo"><input value={data.produto.modelo} onChange={(event) => updateGroup("produto", "modelo", event.target.value)} /></Field>
              <Field label="Cor"><input value={data.produto.cor} onChange={(event) => updateGroup("produto", "cor", event.target.value)} /></Field>
              <Field label="Revestimento"><input value={data.produto.revestimento} onChange={(event) => updateGroup("produto", "revestimento", event.target.value)} /></Field>
              <Field label="Peso"><input value={data.produto.peso} onChange={(event) => updateGroup("produto", "peso", event.target.value)} /></Field>
              <Field label="Garantia"><input value={data.produto.garantia} onChange={(event) => updateGroup("produto", "garantia", event.target.value)} /></Field>
            </div>
          </details>

          <details open>
            <summary><span>06</span> Características resumidas</summary>
            <div className="catalog-field-grid">
              <Field label="Resumo técnico" wide><textarea rows={7} value={data.resumo.caracteristicas} onChange={(event) => updateGroup("resumo", "caracteristicas", event.target.value)} /></Field>
            </div>
          </details>

          {[
            ["07", "Especificações do assento", "assento"],
            ["08", "Especificações do encosto", "encosto"],
            ["09", "Especificações da estrutura", "estrutura"],
          ].map(([number, title, key]) => (
            <details key={key}>
              <summary><span>{number}</span> {title}</summary>
              <div className="catalog-field-grid">
                <Field label={title} wide>
                  <textarea
                    rows={7}
                    value={data.secoes[key as keyof CatalogData["secoes"]]}
                    onChange={(event) => updateGroup("secoes", key as keyof CatalogData["secoes"], event.target.value)}
                  />
                </Field>
              </div>
            </details>
          ))}

          <details>
            <summary><span>10</span> Base, pés, braços, rodízios, mecanismos e acessórios</summary>
            <div className="catalog-field-grid">
              {(["base", "pes", "bracos", "rodizios", "mecanismos", "acessorios"] as const).map((key) => (
                <Field label={TECHNICAL_SECTION_OPTIONS.find((section) => section.key === key)?.label || key} key={key}>
                  <textarea rows={5} value={data.secoes[key]} onChange={(event) => updateGroup("secoes", key, event.target.value)} />
                </Field>
              ))}
            </div>
          </details>

          <details>
            <summary><span>11</span> Dimensões</summary>
            <div className="catalog-field-grid"><Field label="Dimensões" wide><textarea rows={7} value={data.secoes.dimensoes} onChange={(event) => updateGroup("secoes", "dimensoes", event.target.value)} /></Field></div>
          </details>

          <details>
            <summary><span>12</span> Normas e conformidades</summary>
            <div className="catalog-field-grid"><Field label="Normas e certificações" wide><textarea rows={7} value={data.secoes.normas} onChange={(event) => updateGroup("secoes", "normas", event.target.value)} /></Field></div>
          </details>

          <details>
            <summary><span>13</span> Informações complementares</summary>
            <div className="catalog-field-grid">
              <Field label="Informações complementares" wide><textarea rows={6} value={data.secoes.complementares} onChange={(event) => updateGroup("secoes", "complementares", event.target.value)} /></Field>
              <Field label="Observações" wide><textarea rows={5} value={data.secoes.observacoes} onChange={(event) => updateGroup("secoes", "observacoes", event.target.value)} /></Field>
            </div>
          </details>

          <details open>
            <summary><span>14</span> Imagens principais, secundárias e desenhos técnicos</summary>
            <div className="catalog-upload-actions">
              <label className="button button-secondary">
                <Upload size={16} />
                Logo
                <input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) addAsset(file, "logo");
                  event.target.value = "";
                }} />
              </label>
              <label className="button button-secondary">
                <ImagePlus size={16} />
                Imagens do produto
                <input type="file" accept="image/png,image/jpeg,image/webp" multiple hidden onChange={(event) => {
                  addProductImages(event.target.files);
                  event.target.value = "";
                }} />
              </label>
            </div>
            <div className="catalog-assets">
              {assets.map((asset) => (
                <div className="catalog-asset-row" key={asset.id}>
                  <img src={asset.previewUrl} alt="" />
                  <div>
                    <strong>{asset.file.name}</strong>
                    <input
                      aria-label={`Legenda de ${asset.file.name}`}
                      placeholder="Legenda"
                      value={asset.caption}
                      onChange={(event) => updateAsset(asset.id, "caption", event.target.value)}
                    />
                  </div>
                  {asset.role === "logo" ? (
                    <span className="catalog-asset-role">LOGO</span>
                  ) : (
                    <select
                      aria-label={`Tipo de ${asset.file.name}`}
                      value={asset.role}
                      onChange={(event) => updateAsset(asset.id, "role", event.target.value)}
                    >
                      <option value="principal">Principal</option>
                      <option value="secundaria">Secundária</option>
                      <option value="tecnica">Técnica</option>
                    </select>
                  )}
                  {asset.role === "tecnica" && (
                    <select
                      aria-label={`Seção de ${asset.file.name}`}
                      value={asset.section}
                      onChange={(event) => updateAsset(asset.id, "section", event.target.value)}
                    >
                      {TECHNICAL_SECTION_OPTIONS.map((section) => (
                        <option value={section.key} key={section.key}>{section.label}</option>
                      ))}
                    </select>
                  )}
                  <button className="icon-button" type="button" title="Remover imagem" aria-label={`Remover ${asset.file.name}`} onClick={() => removeAsset(asset.id)}>
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {!assets.length && <div className="empty-state">Nenhuma imagem adicionada.</div>}
            </div>
          </details>

          <details>
            <summary><span>15</span> Configuração da marca-d’água</summary>
            <div className="catalog-field-grid">
              <label className="catalog-toggle">
                <input type="checkbox" checked={data.marca_dagua.ativa} onChange={(event) => updateGroup("marca_dagua", "ativa", event.target.checked)} />
                <span>Marca-d’água ativa</span>
              </label>
              <Field label="Texto personalizado" wide><input value={data.marca_dagua.texto_personalizado} onChange={(event) => updateGroup("marca_dagua", "texto_personalizado", event.target.value)} /></Field>
              <Field label="Cor"><input type="color" value={data.marca_dagua.cor} onChange={(event) => updateGroup("marca_dagua", "cor", event.target.value)} /></Field>
              <Field label={`Opacidade: ${data.marca_dagua.opacidade}%`}><input type="range" min={3} max={30} value={data.marca_dagua.opacidade} onChange={(event) => updateGroup("marca_dagua", "opacidade", Number(event.target.value))} /></Field>
            </div>
          </details>
        </div>
      )}

      {tab === "preview" && <CatalogPreview data={data} assets={assets} />}

      {tab === "alertas" && (
        <div className="catalog-alert-panel" ref={alertsPanelRef}>
          <section>
            <h3>Campos obrigatórios</h3>
            {alerts.errors.length ? (
              <ul>{alerts.errors.map((alert) => <li key={alert}>{alert}</li>)}</ul>
            ) : <p>Nenhuma pendência obrigatória.</p>}
          </section>
          <section>
            <h3>Revisões recomendadas</h3>
            {alerts.warnings.length ? (
              <ul>{alerts.warnings.map((alert) => <li key={alert}>{alert}</li>)}</ul>
            ) : <p>Nenhum alerta adicional.</p>}
          </section>
        </div>
      )}

      <div className="catalog-export-bar">
        <button
          className="button button-primary"
          type="button"
          disabled={generating || busy}
          onClick={exportCatalog}
          aria-describedby={alerts.errors.length ? "catalog-export-feedback" : undefined}
        >
          {generating ? <LoaderCircle className="is-spinning" size={17} /> : <FileText size={17} />}
          {generating ? "Gerando catálogo..." : "Gerar catálogo"}
        </button>
        {!generating && alerts.errors.length > 0 && (
          <div className="catalog-export-feedback" id="catalog-export-feedback">
            <AlertTriangle size={17} />
            <span>
              {alerts.errors.length} campo(s) obrigatório(s) pendente(s). Clique para revisar.
            </span>
          </div>
        )}
        {exports && (
          <div className="catalog-downloads" aria-label="Arquivos do catálogo">
            <a className="button button-secondary" href={exports.docx.download_url} download><FileText size={16} />Word</a>
            <a className="button button-secondary" href={exports.pdf.download_url} download><Download size={16} />PDF</a>
            <a className="button button-secondary" href={exports.json.download_url} download><FileJson size={16} />JSON</a>
            <a className="button button-secondary" href={exports.images.download_url} download><FileArchive size={16} />Imagens</a>
          </div>
        )}
      </div>
    </section>
  );
}
