import { useMemo, useRef, useState } from "react";
import { ArrowRight, ChevronLeft, ChevronRight, Search, Trash2 } from "lucide-react";
import { searchBids } from "../api";
import type { Bid, UiMessage } from "../types";
import { localIsoDate, toPncpDate } from "../utils";
import { DateRangePicker } from "./DateRangePicker";
import { KeywordTagInput } from "./KeywordTagInput";
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

export function SearchBlock({ onUseLink }: SearchBlockProps) {
  const searchRequestRef = useRef(0);
  const defaults = useMemo(defaultDates, []);
  const [startDate, setStartDate] = useState(defaults.start);
  const [endDate, setEndDate] = useState(defaults.end);
  const [uf, setUf] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [keywordDraft, setKeywordDraft] = useState("");
  const [objectType, setObjectType] = useState("");
  const [modality, setModality] = useState("6");
  const [results, setResults] = useState<Bid[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [searchingAll, setSearchingAll] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);
  const [busy, setBusy] = useState(false);

  const clear = () => {
    searchRequestRef.current += 1;
    setStartDate("");
    setEndDate("");
    setUf("");
    setKeywords([]);
    setKeywordDraft("");
    setObjectType("");
    setModality("");
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
        uf: uf.trim().toUpperCase(),
        palavraChave: effectiveKeywords.join(";"),
        tipoObjeto: objectType,
        codigoModalidadeContratacao: modality,
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
        <label>
          UF
          <input
            value={uf}
            maxLength={2}
            placeholder="SP"
            onChange={(e) => setUf(e.target.value.replace(/[^a-z]/gi, "").slice(0, 2))}
          />
        </label>
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
                <tr key={`${bid.cnpj}-${bid.ano}-${bid.sequencial}`}>
                  <td>{bid.orgao}</td>
                  <td>{[bid.municipio, bid.uf].filter(Boolean).join(" / ")}</td>
                  <td>{bid.numeroCompra}</td>
                  <td className="description-cell">{bid.objeto}</td>
                  <td>{bid.encerramento ? new Date(bid.encerramento).toLocaleDateString("pt-BR") : ""}</td>
                  <td>
                    <button
                      className="button button-small button-secondary"
                      type="button"
                      onClick={() => onUseLink(bid.link)}
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
    </section>
  );
}
