import type { ProposalItem } from "./types";

export const MAX_TEMPLATE_SIZE = 15 * 1024 * 1024;

export function normalizePncpUrl(value: string): string | null {
  try {
    const trimmed = value.trim().replace(/^["']|["']$/g, "");
    if (!trimmed) return null;

    let candidate = trimmed;
    if (candidate.startsWith("/app/editais/")) {
      candidate = `https://pncp.gov.br${candidate}`;
    } else if (!/^https?:\/\//i.test(candidate)) {
      candidate = `https://${candidate}`;
    }

    const url = new URL(candidate);
    const hostname = url.hostname.toLowerCase().replace(/^www\./, "");
    if (!["http:", "https:"].includes(url.protocol) || hostname !== "pncp.gov.br") {
      return null;
    }

    const match = url.pathname.match(
      /^\/app\/editais\/(\d{14})\/(\d{4})\/(\d+)\/?$/i,
    );
    if (!match) return null;

    const [, cnpj, year, sequence] = match;
    return `https://pncp.gov.br/app/editais/${cnpj}/${year}/${sequence}`;
  } catch {
    return null;
  }
}

export function isValidPncpUrl(value: string): boolean {
  return normalizePncpUrl(value) !== null;
}

export function itemKey(item: Pick<ProposalItem, "lote" | "item">): string {
  const itemNumber = String(item.item || "").trim().replace(/^0+(?=\d)/, "");
  const lot = String(item.lote || "").trim().replace(/^0+(?=\d)/, "");
  return lot ? `${lot}/${itemNumber}` : itemNumber;
}

export function parseMoneyToCents(value: string): bigint | null {
  const text = String(value || "")
    .replace(/R\$/gi, "")
    .replace(/\s/g, "")
    .trim();
  if (!text || text.startsWith("-")) return null;
  const normalized = text.includes(",")
    ? text.replace(/\./g, "").replace(",", ".")
    : text;
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) return null;
  const [integer, decimal = ""] = normalized.split(".");
  return BigInt(integer) * 100n + BigInt(decimal.padEnd(2, "0"));
}

export function formatCents(cents: bigint): string {
  const absolute = cents < 0n ? -cents : cents;
  const integer = absolute / 100n;
  const decimal = String(absolute % 100n).padStart(2, "0");
  const grouped = integer.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${cents < 0n ? "-" : ""}R$ ${grouped},${decimal}`;
}

export function normalizeMoney(value: string): string | null {
  const cents = parseMoneyToCents(value);
  return cents === null ? null : formatCents(cents);
}

function parseDecimal(value: string | number | null): { coefficient: bigint; scale: number } | null {
  const normalized = String(value ?? "").trim().replace(/\./g, "").replace(",", ".");
  if (!/^\d+(?:\.\d+)?$/.test(normalized)) return null;
  const [integer, decimal = ""] = normalized.split(".");
  return {
    coefficient: BigInt(`${integer}${decimal}`),
    scale: decimal.length,
  };
}

export function calculateItemTotal(quantity: string | number | null, unitValue: string): string {
  const parsedQuantity = parseDecimal(quantity);
  const unitCents = parseMoneyToCents(unitValue);
  if (!parsedQuantity || unitCents === null) return "";
  const divisor = 10n ** BigInt(parsedQuantity.scale);
  const numerator = parsedQuantity.coefficient * unitCents;
  const roundedCents = (numerator + divisor / 2n) / divisor;
  return formatCents(roundedCents);
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function validateTemplateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".docx")) {
    return "Selecione um arquivo Word no formato .docx.";
  }
  if (!file.size) return "O arquivo selecionado está vazio.";
  if (file.size > MAX_TEMPLATE_SIZE) return "O arquivo excede o limite de 15 MB.";
  return null;
}

export function toPncpDate(value: string): string {
  return value.replace(/-/g, "");
}

export function localIsoDate(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function parseLocalDate(value: string): Date {
  const normalized = /^\d{4}-\d{2}-\d{2}$/.test(value.trim())
    ? `${value.trim()}T00:00:00`
    : value;
  return new Date(normalized);
}
