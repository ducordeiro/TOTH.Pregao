import type { CatalogAsset, CatalogData } from "../types";

export const TECHNICAL_SECTION_OPTIONS = [
  { key: "assento", label: "ASSENTO" },
  { key: "encosto", label: "ENCOSTO" },
  { key: "estrutura", label: "ESTRUTURA" },
  { key: "base", label: "BASE" },
  { key: "pes", label: "PÉS" },
  { key: "bracos", label: "BRAÇOS" },
  { key: "rodizios", label: "RODÍZIOS" },
  { key: "mecanismos", label: "MECANISMOS" },
  { key: "acessorios", label: "ACESSÓRIOS" },
  { key: "dimensoes", label: "DIMENSÕES" },
  { key: "normas", label: "NORMAS E CONFORMIDADES" },
  { key: "complementares", label: "INFORMAÇÕES COMPLEMENTARES" },
  { key: "observacoes", label: "OBSERVAÇÕES" },
] as const;

function chunkText(value: string, maximum = 1600): string[] {
  const text = value.trim();
  if (!text) return [];
  const paragraphs = text.split(/\n+/).map((part) => part.trim()).filter(Boolean);
  const chunks: string[] = [];
  let current = "";
  for (const paragraph of paragraphs) {
    if (!current) {
      current = paragraph;
      continue;
    }
    if (`${current}\n${paragraph}`.length <= maximum) {
      current = `${current}\n${paragraph}`;
      continue;
    }
    chunks.push(current);
    current = paragraph;
  }
  if (current) chunks.push(current);
  return chunks;
}

function watermarkText(data: CatalogData): string {
  if (data.marca_dagua.texto_personalizado.trim()) {
    return data.marca_dagua.texto_personalizado.trim();
  }
  return [
    data.fabricante.razao_social,
    data.fabricante.cnpj,
    data.orgao.nome,
    data.documento_licitacao.numero_pregao
      ? `Pregão ${data.documento_licitacao.numero_pregao}`
      : "",
  ].filter(Boolean).join(" | ");
}

function Watermark({ data }: { data: CatalogData }) {
  if (!data.marca_dagua.ativa || !watermarkText(data)) return null;
  return (
    <div
      className="catalog-watermark"
      style={{
        color: data.marca_dagua.cor,
        opacity: data.marca_dagua.opacidade / 100,
      }}
    >
      {watermarkText(data)}
    </div>
  );
}

function PreviewImage({
  asset,
  className,
}: {
  asset?: CatalogAsset;
  className: string;
}) {
  if (!asset) return <div className={`${className} is-empty`}>IMAGEM NÃO INFORMADA</div>;
  return (
    <figure className={className}>
      <img src={asset.previewUrl} alt={asset.caption || asset.file.name} />
      {(asset.caption || asset.file.name) && (
        <figcaption>{asset.caption || asset.file.name}</figcaption>
      )}
    </figure>
  );
}

function PageNumber({ current, total }: { current: number; total: number }) {
  return <div className="catalog-page-number">Página {current} de {total}</div>;
}

interface CatalogPreviewProps {
  data: CatalogData;
  assets: CatalogAsset[];
}

export function CatalogPreview({ data, assets }: CatalogPreviewProps) {
  const logo = assets.find((asset) => asset.role === "logo");
  const mainImage = assets.find((asset) => asset.role === "principal");
  const technicalPages = TECHNICAL_SECTION_OPTIONS.flatMap((section) => {
    const chunks = chunkText(data.secoes[section.key]);
    const images = assets.filter(
      (asset) => asset.role === "tecnica" && asset.section === section.key,
    );
    const count = Math.max(chunks.length, images.length ? 1 : 0);
    return Array.from({ length: count }, (_, index) => ({
      key: `${section.key}-${index}`,
      title: section.label,
      continuation: index > 0,
      text: chunks[index] || "",
      images: index === 0 ? images : [],
    }));
  });
  const secondaryPages = assets
    .filter((asset) => asset.role === "secundaria")
    .map((asset) => ({
      key: asset.id,
      title: "IMAGEM SECUNDÁRIA",
      asset,
    }));
  const totalPages = 1 + technicalPages.length + secondaryPages.length;

  return (
    <div className="catalog-preview-pages">
      <article className="catalog-sheet">
        <Watermark data={data} />
        <header className="catalog-document-header">
          <div className="catalog-logo-preview">
            {logo ? <img src={logo.previewUrl} alt="Logo da empresa" /> : <span>LOGO</span>}
          </div>
          <div>
            <h2>{data.documento_licitacao.titulo || "CATÁLOGO TÉCNICO"}</h2>
            <p><strong>Pregão:</strong> {data.documento_licitacao.numero_pregao}</p>
            <p><strong>Processo:</strong> {data.documento_licitacao.processo}</p>
            <p><strong>Órgão:</strong> {data.orgao.nome}</p>
          </div>
        </header>

        <h3>IDENTIFICAÇÃO DO FABRICANTE</h3>
        <dl className="catalog-identification-grid">
          <dt>Razão social</dt><dd>{data.fabricante.razao_social}</dd>
          <dt>Nome fantasia</dt><dd>{data.fabricante.nome_fantasia}</dd>
          <dt>CNPJ</dt><dd>{data.fabricante.cnpj}</dd>
          <dt>Endereço</dt><dd>{data.fabricante.endereco}</dd>
        </dl>

        <h3>ITEM {data.item.numero}</h3>
        <p className="catalog-item-description">{data.item.descricao}</p>
        <dl className="catalog-identification-grid is-compact">
          <dt>Marca</dt><dd>{data.produto.marca}</dd>
          <dt>Modelo</dt><dd>{data.produto.modelo}</dd>
        </dl>

        <PreviewImage asset={mainImage} className="catalog-main-image" />

        <h3>INFORMAÇÕES RESUMIDAS</h3>
        <dl className="catalog-summary-grid">
          <div><dt>Cor</dt><dd>{data.produto.cor}</dd></div>
          <div><dt>Revestimento</dt><dd>{data.produto.revestimento}</dd></div>
          <div><dt>Peso</dt><dd>{data.produto.peso}</dd></div>
          <div><dt>Normas</dt><dd>{data.secoes.normas}</dd></div>
        </dl>
        <p className="catalog-summary-text">{data.resumo.caracteristicas}</p>
        <PageNumber current={1} total={totalPages} />
      </article>

      {technicalPages.map((page, index) => (
        <article className="catalog-sheet" key={page.key}>
          <Watermark data={data} />
          <div className="catalog-running-header">
            <span>{data.fabricante.nome_fantasia || data.fabricante.razao_social}</span>
            <span>Item {data.item.numero} · {data.produto.marca} {data.produto.modelo}</span>
          </div>
          <h3>{page.title}{page.continuation ? " — CONTINUAÇÃO" : ""}</h3>
          {page.text && <p className="catalog-technical-text">{page.text}</p>}
          <div className="catalog-technical-images">
            {page.images.map((asset) => (
              <PreviewImage
                asset={asset}
                className="catalog-technical-image"
                key={asset.id}
              />
            ))}
          </div>
          <PageNumber current={index + 2} total={totalPages} />
        </article>
      ))}

      {secondaryPages.map((page, index) => (
        <article className="catalog-sheet" key={page.key}>
          <Watermark data={data} />
          <div className="catalog-running-header">
            <span>{data.fabricante.nome_fantasia || data.fabricante.razao_social}</span>
            <span>Item {data.item.numero}</span>
          </div>
          <h3>{page.title}</h3>
          <PreviewImage asset={page.asset} className="catalog-secondary-image" />
          <PageNumber
            current={technicalPages.length + index + 2}
            total={totalPages}
          />
        </article>
      ))}
    </div>
  );
}
