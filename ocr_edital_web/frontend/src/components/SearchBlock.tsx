import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowRight, ChevronDown, ChevronLeft, ChevronRight, Search, Trash2 } from "lucide-react";
import { searchBids } from "../api";
import type { Bid, UiMessage } from "../types";
import { localIsoDate, toPncpDate } from "../utils";
import { DateRangePicker } from "./DateRangePicker";
import { KeywordTagInput } from "./KeywordTagInput";
import { OpportunityDetailModal } from "./OpportunityDetailModal";
import { StatusMessage } from "./StatusMessage";

interface SearchBlockProps {
  onUseLink: (link: string) => void;
}

function defaultDates() {
  const start = new Date();
  const end = new Date(start);
  end.setDate(end.getDate() + 29);
  return { start: localIsoDate(start), end: localIsoDate(end) };
}

const PAGE_SIZE = 10;

const BRAZILIAN_UFS = [
  ["AC", "Acre"],
  ["AL", "Alagoas"],
  ["AP", "Amapa"],
  ["AM", "Amazonas"],
  ["BA", "Bahia"],
  ["CE", "Ceara"],
  ["DF", "Distrito Federal"],
  ["ES", "Espirito Santo"],
  ["GO", "Goias"],
  ["MA", "Maranhao"],
  ["MT", "Mato Grosso"],
  ["MS", "Mato Grosso do Sul"],
  ["MG", "Minas Gerais"],
  ["PA", "Para"],
  ["PB", "Paraiba"],
  ["PR", "Parana"],
  ["PE", "Pernambuco"],
  ["PI", "Piaui"],
  ["RJ", "Rio de Janeiro"],
  ["RN", "Rio Grande do Norte"],
  ["RS", "Rio Grande do Sul"],
  ["RO", "Rondonia"],
  ["RR", "Roraima"],
  ["SC", "Santa Catarina"],
  ["SP", "Sao Paulo"],
  ["SE", "Sergipe"],
  ["TO", "Tocantins"],
] as const;

export function SearchBlock({ onUseLink }: SearchBlockProps) {
  const searchRequestRef = useRef(0);
  const ufFieldRef = useRef<HTMLDivElement>(null);
  const defaults = useMemo(defaultDates, []);
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);
  const [ufs, setUfs] = useState<string[]>([]);
  const [ufMenuOpen, setUfMenuOpen] = useState(false);
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordDraft, setKeywordDraft] = useState("");
  const [objectType, setObjectType] = useState("");
  const [modality, setModality] = useState("6");
  const [purchaseNumber, setPurchaseNumber] = useState("");
  const [uasg, setUasg] = useState("");
  const [results, setResults] = useState<Bid[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [searchingAll, setSearchingAll] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedBid, setSelectedBid] = useState<Bid | null>(null);

  useEffect(() => {
    if (!ufMenuOpen) return;
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!ufFieldRef.current?.contains(event.target as Node)) setUfMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, [ufMenuOpen]);

  const clear = () => {
    searchRequestRef.current += 1;
    setStartDate("");
    setEndDate("");
    setUfs([]);
    setUfMenuOpen(false);
    setKeywords([]);
    setKeywordDraft("");
    setObjectType("");
    setModality("");
    setPurchaseNumber("");
    setUasg("");
    setResults([]);
    setPage(1);
    setTotal(0);
    setTotalPages(0);
    setSearchingAll(false);
    setBusy(false);
    setMessage({ kind: "info", text: "Filtros limpos." });
  };

  const runSearch = async (targetPage: number) => {
    if ((startDate && !endDate) || (!startDate && endDate)) {
      setMessage({ kind: "warning", text: "Selecione as datas inicial e final." });
      return;
    }
    if (startDate && endDate) {
      const start = new Date(`${startDate}T00:00:00`);
      const end = new Date(`${endDate}T00:00:00`);
      const days = Math.round((end.getTime() - start.getTime()) / 86_400_000) + 1;
      if (days < 1 || days > 30) {
        setMessage({ kind: "warning", text: "Selecione um período de até 30 dias." });
        return;
      }
    }
    if (startDate && endDate && endDate < startDate) {
      setMessage({ kind: "warning", text: "A data final deve ser posterior à data inicial." });
      return;
    }
    const requestId = searchRequestRef.current + 1;
    searchRequestRef.current = requestId;
    setBusy(true);
    setSearchingAll(false);
    setMessage({ kind: "info", text: "Consultando contratações no PNCP..." });
    try {
      const effectiveKeywords = [
        ...keywords,
        ...(keywordDraft.trim() ? [keywordDraft.trim()] : []),
      ].filter(
        (term, index, all) =>
          all.findIndex(
            (candidate) =>
              candidate.toLocaleLowerCase("pt-BR") === term.toLocaleLowerCase("pt-BR"),
          ) === index,
      );
      const params = new URLSearchParams({
        dataInicial: toPncpDate(startDate),
        dataFinal: toPncpDate(endDate),
        uf: ufs.join(","),
        palavraChave: effectiveKeywords.join(";"),
        tipoObjeto: objectType,
        codigoModalidadeContratacao: modality,
        numeroCompra: purchaseNumber.trim(),
        uasg: uasg.trim(),
        pagina: String(targetPage),
        tamanhoPagina: String(PAGE_SIZE),
        rapido: "1",
      });
      let payload = await searchBids(params);
      for (let poll = 0; poll < 90; poll += 1) {
        if (requestId !== searchRequestRef.current) return;
        const nextResults = payload.results || [];
        const nextPage = payload.pagina || targetPage;
        const nextTotal = payload.total || 0;
        const nextTotalPages =
          payload.total_pages ?? (nextTotal ? Math.ceil(nextTotal / PAGE_SIZE) : 0);
        setResults(nextResults);
        setPage(nextPage);
        setTotal(nextTotal);
        setTotalPages(nextTotalPages);
        setSearchingAll(Boolean(payload.searching));
        setBusy(false);
        setMessage({
          kind: payload.searching
            ? "info"
            : payload.complete === false
              ? "warning"
              : nextResults.length
                ? "success"
                : "warning",
          text: payload.searching
            ? `Exibindo ${nextResults.length} edital(is) iniciais. A busca completa continua em segundo plano.`
            : payload.complete === false
              ? `Foram encontrados ${nextTotal.toLocaleString("pt-BR")} edital(is), mas o PNCP não respondeu a todas as páginas. Tente novamente para completar a consulta.`
              : nextResults.length
                ? `${nextResults.length} edital(is) nesta página, de ${nextTotal.toLocaleString("pt-BR")} encontrado(s) com todos os filtros.`
                : nextTotal
                  ? "Nenhum edital desta página corresponde aos filtros utilizados."
                  : "Nenhum edital encontrado com estes filtros.",
        });
        if (!payload.searching) break;
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        if (requestId !== searchRequestRef.current) return;
        payload = await searchBids(params);
      }
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível consultar o PNCP.",
      });
    } finally {
      if (requestId === searchRequestRef.current) setBusy(false);
    }
  };

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    void runSearch(1);
  };

  return (
    <section className="workspace-section" aria-labelledby="search-heading">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Bloco 1</span>
          <h2 id="search-heading">Consulta PNCP</h2>
          <p>Localize contratações abertas e use o link oficial na proposta.</p>
        </div>
      </div>

      <form className="search-form" onSubmit={submit}>
        <div className="period-field">
          <span className="field-label">Período</span>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={(start, end) => {
              setStartDate(start);
              setEndDate(end);
            }}
          />
          <small>Selecione um período de até 30 dias.</small>
        </div>
        <div className="uf-field" ref={ufFieldRef}>
          <span className="field-label">UF</span>
          <button
            className="uf-multi-trigger"
            type="button"
            aria-label="Selecionar UFs da oportunidade"
            aria-haspopup="listbox"
            aria-expanded={ufMenuOpen}
            onClick={() => setUfMenuOpen((current) => !current)}
          >
            <span>
              {ufs.length === 0
                ? "Todos os estados"
                : ufs.length <= 3
                  ? ufs.join(", ")
                  : `${ufs.slice(0, 3).join(", ")} +${ufs.length - 3}`}
            </span>
            <ChevronDown size={16} aria-hidden="true" />
          </button>
          {ufMenuOpen && (
            <div
              className="uf-multi-menu"
              role="listbox"
              aria-label="Estados selecionados"
              aria-multiselectable="true"
            >
              <button
                className={ufs.length === 0 ? "is-active" : ""}
                type="button"
                onClick={() => setUfs([])}
              >
                Todos os estados
              </button>
              <div className="uf-option-list">
                {BRAZILIAN_UFS.map(([code, name]) => {
                  const checked = ufs.includes(code);
                  return (
                    <label key={code} role="option" aria-selected={checked}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          setUfs((current) => {
                            const selected = new Set(current);
                            if (event.target.checked) selected.add(code);
                            else selected.delete(code);
                            return BRAZILIAN_UFS
                              .map(([ufCode]) => ufCode)
                              .filter((ufCode) => selected.has(ufCode));
                          });
                        }}
                      />
                      <span><strong>{code}</strong>{name}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>
        <div className="keyword-field">
          <span className="field-label">Palavras-chave</span>
          <KeywordTagInput
            terms={keywords}
            draft={keywordDraft}
            onTermsChange={setKeywords}
            onDraftChange={setKeywordDraft}
          />
          <small>Separe cada referência com ponto e vírgula (;).</small>
        </div>
        <label>
          Tipo do objeto
          <select value={objectType} onChange={(e) => setObjectType(e.target.value)}>
            <option value="">Materiais e serviços</option>
            <option value="material">Materiais</option>
            <option value="servico">Serviços</option>
          </select>
        </label>
        <label>
          Modalidade
          <select value={modality} onChange={(e) => setModality(e.target.value)}>
            <option value="6">Pregão eletrônico</option>
            <option value="8">Dispensa eletrônica</option>
            <option value="">Todas</option>
          </select>
        </label>
        <label>
          Número da compra
          <input
            value={purchaseNumber}
            maxLength={80}
            placeholder="Ex.: 90010/2026"
            onChange={(event) => setPurchaseNumber(event.target.value)}
          />
        </label>
        <label>
          UASG
          <input
            value={uasg}
            inputMode="numeric"
            maxLength={20}
            placeholder="Ex.: 123456"
            onChange={(event) => setUasg(event.target.value.replace(/\D/g, ""))}
          />
        </label>
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={busy}>
            <Search size={17} />
            {busy ? "Consultando..." : "Buscar contratações"}
          </button>
          <button className="button button-secondary" type="button" disabled={busy} onClick={clear}>
            <Trash2 size={17} />
            Limpar
          </button>
        </div>
      </form>

      <StatusMessage message={message} />

      <div className="data-table-wrap search-results">
        {results.length ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Órgão</th>
                <th>Local</th>
                <th>Número</th>
                <th>Objeto</th>
                <th>Encerramento</th>
                <th aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {results.map((bid) => (
                <tr
                  className="search-result-row"
                  key={`${bid.cnpj}-${bid.ano}-${bid.sequencial}`}
                  tabIndex={0}
                  role="button"
                  aria-label={`Abrir oportunidade ${bid.numeroCompra}`}
                  onClick={() => setSelectedBid(bid)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelectedBid(bid);
                    }
                  }}
                >
                  <td>{bid.orgao}</td>
                  <td>{[bid.municipio, bid.uf].filter(Boolean).join(" / ")}</td>
                  <td>{bid.numeroCompra}</td>
                  <td className="description-cell">{bid.objeto}</td>
                  <td>{bid.encerramento ? new Date(bid.encerramento).toLocaleDateString("pt-BR") : ""}</td>
                  <td>
                    <button
                      className="button button-small button-secondary"
                      type="button"
                      title="Usar oportunidade no Bloco 2"
                      onClick={(event) => {
                        event.stopPropagation();
                        onUseLink(bid.link);
                      }}
                    >
                      Usar
                      <ArrowRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="empty-state">Use os filtros para consultar contratações abertas.</div>
        )}
      </div>

      {totalPages > 0 && !searchingAll ? (
        <nav className="search-pagination" aria-label="Paginação das oportunidades">
          <span>
            Página {page.toLocaleString("pt-BR")} de {totalPages.toLocaleString("pt-BR")} ·{" "}
            {total.toLocaleString("pt-BR")} edital(is) filtrado(s)
          </span>
          <div className="search-pagination-actions">
            <button
              className="button button-small button-secondary"
              type="button"
              disabled={busy || page <= 1}
              onClick={() => void runSearch(page - 1)}
            >
              <ChevronLeft size={16} />
              Anterior
            </button>
            <button
              className="button button-small button-secondary"
              type="button"
              disabled={busy || page >= totalPages}
              onClick={() => void runSearch(page + 1)}
            >
              Próxima
              <ChevronRight size={16} />
            </button>
          </div>
        </nav>
      ) : null}

      <OpportunityDetailModal
        bid={selectedBid}
        onClose={() => setSelectedBid(null)}
        onUseLink={onUseLink}
      />
    </section>
  );
}
