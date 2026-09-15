import { memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { TemplatePagePartsPreview } from "../types";

interface RenderedParts {
  styles: HTMLElement;
  pages: HTMLElement[];
}

const cache = new Map<string, Promise<RenderedParts>>();

function renderParts(base64: string): Promise<RenderedParts> {
  const previous = cache.get(base64);
  if (previous) return previous;
  const pending = (async () => {
    const { renderAsync } = await import("docx-preview");
    const body = document.createElement("div");
    const styles = document.createElement("div");
    const bytes = Uint8Array.from(atob(base64), (character) => character.charCodeAt(0));
    await renderAsync(bytes, body, styles, {
      className: "toth-template-docx", inWrapper: true, breakPages: true,
      renderHeaders: true, renderFooters: true, useBase64URL: true,
      renderAltChunks: false, renderComments: false, renderFootnotes: false,
      renderEndnotes: false, ignoreLastRenderedPageBreak: true,
    });
    // Word on this machine substitutes Calibri when Aptos is unavailable.
    // Keep Aptos first (including embedded fonts), instead of a serif browser fallback.
    for (const element of body.querySelectorAll<HTMLElement>("[style]")) {
      if (/\bAptos\b/i.test(element.style.fontFamily)) {
        element.style.fontFamily += ", Calibri, Arial, sans-serif";
      }
    }
    await Promise.all(Array.from(body.querySelectorAll("img")).map((image) => image.decode().catch(() => undefined)));
    return { styles, pages: Array.from(body.querySelectorAll<HTMLElement>("section.toth-template-docx")) };
  })();
  cache.set(base64, pending);
  if (cache.size > 3) cache.delete(cache.keys().next().value!);
  void pending.catch(() => { if (cache.get(base64) === pending) cache.delete(base64); });
  return pending;
}

interface TemplatePagePartProps {
  preview: TemplatePagePartsPreview;
  kind: "header" | "footer";
  pageIndex: number;
  onHeight: (kind: "header" | "footer", heightPt: number) => void;
}

export const TemplatePagePart = memo(function TemplatePagePart({ preview, kind, pageIndex, onHeight }: TemplatePagePartProps) {
  const host = useRef<HTMLDivElement>(null);
  const [rendered, setRendered] = useState<{ key: string; parts: RenderedParts } | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    setFailed(false);
    void renderParts(preview.docx_base64).then((parts) => {
      if (!cancelled) setRendered({ key: preview.docx_base64, parts });
    }).catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [preview.docx_base64]);

  useLayoutEffect(() => {
    const element = host.current;
    if (!element) return;
    const shadow = element.shadowRoot || element.attachShadow({ mode: "open" });
    shadow.replaceChildren();
    if (!rendered || rendered.key !== preview.docx_base64) return;
    const variant = pageIndex === 0 ? 0 : pageIndex % 2 === 1 ? 1 : 2;
    if ((variant === 0 && preview[`first_${kind}_blank`]) || (variant === 1 && preview[`even_${kind}_blank`])) return;
    const page = rendered.parts.pages[variant] || rendered.parts.pages[0];
    const part = page?.querySelector(kind);
    if (!part) return;
    const section = page.cloneNode(false) as HTMLElement;
    const clone = part.cloneNode(true) as HTMLElement;
    clone.style.margin = "0";
    clone.style.minHeight = "0";
    // Keep document styles isolated from the app's table/header rules.
    Object.assign(section.style, { width: `${preview.content_width_pt}pt`, minHeight: "0", padding: "0", margin: "0", boxShadow: "none", overflow: "visible" });
    section.append(clone);
    for (const link of section.querySelectorAll("a")) link.removeAttribute("href");
    const wrapper = document.createElement("div");
    wrapper.className = "toth-template-docx-wrapper";
    Object.assign(wrapper.style, { padding: "0", margin: "0", background: "transparent", width: `${preview.content_width_pt}pt` });
    wrapper.append(section);
    const defaults = document.createElement("style");
    const padding = preview.default_cell_padding_pt;
    defaults.textContent = `.toth-template-docx table { table-layout: fixed; } .toth-template-docx td,.toth-template-docx th { padding: ${padding.top}pt ${padding.right}pt ${padding.bottom}pt ${padding.left}pt; }`;
    shadow.append(defaults, rendered.parts.styles.cloneNode(true), wrapper);
    for (const name of ["--docx-minorHAnsi-font", "--docx-majorHAnsi-font"]) {
      const family = getComputedStyle(section).getPropertyValue(name);
      if (/\bAptos\b/i.test(family)) section.style.setProperty(name, `${family}, Calibri, Arial, sans-serif`);
    }
    let disposed = false;
    const update = () => {
      if (disposed) return;
      const width = element.getBoundingClientRect().width;
      if (!width) return;
      const scale = width / (preview.content_width_pt * 96 / 72);
      wrapper.style.zoom = String(scale);
      onHeight(kind, clone.getBoundingClientRect().height / scale * 72 / 96);
    };
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    void document.fonts.ready.then(update);
    return () => { disposed = true; observer.disconnect(); };
  }, [rendered, preview, kind, pageIndex, onHeight]);

  return (
    <div className="proposal-template-page-part-wrap">
      {failed && <span role="alert">Não foi possível renderizar o {kind === "header" ? "cabeçalho" : "rodapé"} do template.</span>}
      <div ref={host} className="proposal-template-page-part" aria-label={kind === "header" ? "Cabeçalho original do template" : "Rodapé original do template"} />
    </div>
  );
});
