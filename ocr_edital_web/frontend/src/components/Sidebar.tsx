import { BookOpen, BriefcaseBusiness, ClipboardList, Columns3, FileSearch, FileText } from "lucide-react";

export type ActiveBlock = "search" | "proposal" | "catalog" | "business" | "structure" | "flow";

interface SidebarProps {
  active: ActiveBlock;
  onChange: (block: ActiveBlock) => void;
}

export function Sidebar({ active, onChange }: SidebarProps) {
  return (
    <aside className="app-sidebar" aria-label="Navegação principal">
      <div className="app-brand">TOTH</div>
      <nav className="block-navigation" aria-label="Etapas da proposta">
        <button
          className={`block-nav-item${active === "search" ? " is-active" : ""}`}
          type="button"
          onClick={() => onChange("search")}
        >
          <span className="block-nav-number">01</span>
          <FileSearch size={18} aria-hidden="true" />
          <span className="block-nav-copy">
            <strong>Bloco 1</strong>
            <small>Consulta PNCP</small>
          </span>
        </button>
        <button
          className={`block-nav-item${active === "proposal" ? " is-active" : ""}`}
          type="button"
          onClick={() => onChange("proposal")}
        >
          <span className="block-nav-number">02</span>
          <FileText size={18} aria-hidden="true" />
          <span className="block-nav-copy">
            <strong>Bloco 2</strong>
            <small>Gerar proposta</small>
          </span>
        </button>
        <button
          className={`block-nav-item${active === "catalog" ? " is-active" : ""}`}
          type="button"
          onClick={() => onChange("catalog")}
        >
          <span className="block-nav-number">03</span>
          <BookOpen size={18} aria-hidden="true" />
          <span className="block-nav-copy">
            <strong>Bloco 3</strong>
            <small>Catálogo técnico</small>
          </span>
        </button>
        <button
          className={`block-nav-item${active === "business" ? " is-active" : ""}`}
          type="button"
          onClick={() => onChange("business")}
        >
          <span className="block-nav-number">04</span>
          <BriefcaseBusiness size={18} aria-hidden="true" />
          <span className="block-nav-copy">
            <strong>Bloco 4</strong>
            <small>Negócios</small>
          </span>
        </button>
        <button
          className={`block-nav-item${active === "structure" ? " is-active" : ""}`}
          type="button"
          onClick={() => onChange("structure")}
        >
          <span className="block-nav-number">05</span>
          <ClipboardList size={18} aria-hidden="true" />
          <span className="block-nav-copy">
            <strong>Bloco 5</strong>
            <small>Estrutura</small>
          </span>
        </button>
        <button className={`block-nav-item${active === "flow" ? " is-active" : ""}`} type="button" onClick={() => onChange("flow")}>
          <span className="block-nav-number">06</span><Columns3 size={18} aria-hidden="true" />
          <span className="block-nav-copy"><strong>Bloco 6</strong><small>Fluxo de propostas</small></span>
        </button>
      </nav>
      <div className="sidebar-context">Licitações públicas</div>
    </aside>
  );
}
