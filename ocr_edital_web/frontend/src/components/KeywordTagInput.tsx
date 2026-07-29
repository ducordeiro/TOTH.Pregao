import { Search, X } from "lucide-react";

interface KeywordTagInputProps {
  terms: string[];
  draft: string;
  onTermsChange: (terms: string[]) => void;
  onDraftChange: (draft: string) => void;
}

function appendUniqueTerms(current: string[], additions: string[]): string[] {
  const next = [...current];
  const existing = new Set(current.map((term) => term.toLocaleLowerCase("pt-BR")));
  for (const addition of additions) {
    const term = addition.trim();
    const key = term.toLocaleLowerCase("pt-BR");
    if (!term || existing.has(key)) continue;
    existing.add(key);
    next.push(term);
  }
  return next;
}

export function KeywordTagInput({
  terms,
  draft,
  onTermsChange,
  onDraftChange,
}: KeywordTagInputProps) {
  const commitDraft = () => {
    const next = appendUniqueTerms(terms, [draft]);
    if (next.length !== terms.length) onTermsChange(next);
    onDraftChange("");
  };

  const handleChange = (value: string) => {
    if (!value.includes(";")) {
      onDraftChange(value);
      return;
    }
    const parts = value.split(";");
    const remainder = parts.pop() || "";
    onTermsChange(appendUniqueTerms(terms, parts));
    onDraftChange(remainder.replace(/^\s+/, ""));
  };

  const clearAll = () => {
    onTermsChange([]);
    onDraftChange("");
  };

  return (
    <div className="keyword-input-shell">
      <Search className="keyword-leading-icon" size={18} aria-hidden="true" />
      <div className="keyword-token-area">
        {terms.map((term) => (
          <span className="keyword-token" key={term.toLocaleLowerCase("pt-BR")}>
            <span title={term}>{term}</span>
            <button
              type="button"
              title={`Remover ${term}`}
              aria-label={`Remover palavra-chave ${term}`}
              onClick={() => onTermsChange(terms.filter((item) => item !== term))}
            >
              <X size={14} />
            </button>
          </span>
        ))}
        <input
          value={draft}
          maxLength={120}
          aria-label="Adicionar palavra-chave"
          placeholder={terms.length ? "" : "Ex.: cadeira de rodas; monitor;"}
          onChange={(event) => handleChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && draft.trim()) {
              event.preventDefault();
              commitDraft();
            } else if (event.key === "Backspace" && !draft && terms.length) {
              onTermsChange(terms.slice(0, -1));
            }
          }}
        />
      </div>
      {(terms.length > 0 || draft) && (
        <button
          className="keyword-clear-button"
          type="button"
          title="Limpar palavras-chave"
          aria-label="Limpar palavras-chave"
          onClick={clearAll}
        >
          <X size={18} />
        </button>
      )}
    </div>
  );
}
