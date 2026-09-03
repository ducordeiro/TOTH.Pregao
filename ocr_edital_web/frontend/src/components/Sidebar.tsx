import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
import {
  BriefcaseBusiness,
  FileSearch,
  FileSpreadsheet,
  FileText,
  PanelLeftOpen,
} from "lucide-react";
import tothLogo from "../assets/toth-logo.png";

export type ActiveBlock = "search" | "proposal" | "business" | "catalogGenerator";

interface SidebarProps {
  active: ActiveBlock;
  onChange: (block: ActiveBlock) => void;
}

const SIDEBAR_CLOSE_GRACE_MS = 140;

export function Sidebar({ active, onChange }: SidebarProps) {
  const [isOpen, setIsOpen] = useState(false);
  const edgeTriggerRef = useRef<HTMLButtonElement>(null);
  const closeTimerRef = useRef<number | null>(null);
  const restoringTriggerFocusRef = useRef(false);

  function cancelScheduledClose() {
    if (closeTimerRef.current === null) return;
    window.clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }

  function openSidebar() {
    cancelScheduledClose();
    setIsOpen(true);
  }

  function closeSidebar() {
    cancelScheduledClose();
    setIsOpen(false);
  }

  function scheduleSidebarClose() {
    cancelScheduledClose();
    const focusedElement = document.activeElement;
    if (focusedElement instanceof HTMLElement && focusedElement.closest("#app-sidebar")) {
      return;
    }
    closeTimerRef.current = window.setTimeout(() => {
      closeTimerRef.current = null;
      setIsOpen(false);
    }, SIDEBAR_CLOSE_GRACE_MS);
  }

  useEffect(() => () => cancelScheduledClose(), []);

  function handleSidebarBlur(event: FocusEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      closeSidebar();
    }
  }

  function handleSidebarKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape") return;
    closeSidebar();
    restoringTriggerFocusRef.current = true;
    edgeTriggerRef.current?.focus({ preventScroll: true });
  }

  function handleTriggerFocus() {
    if (restoringTriggerFocusRef.current) {
      restoringTriggerFocusRef.current = false;
      return;
    }
    openSidebar();
  }

  return (
    <>
      <button
        ref={edgeTriggerRef}
        className={`sidebar-edge-trigger${isOpen ? " is-open" : ""}`}
        type="button"
        aria-label="Abrir menu principal"
        aria-controls="app-sidebar"
        aria-expanded={isOpen}
        onClick={openSidebar}
        onFocus={handleTriggerFocus}
        onPointerEnter={openSidebar}
      >
        <PanelLeftOpen size={18} aria-hidden="true" />
      </button>
      <aside
        id="app-sidebar"
        className={`app-sidebar${isOpen ? " is-open" : ""}`}
        aria-label="Navegação principal"
        onBlur={handleSidebarBlur}
        onFocus={openSidebar}
        onKeyDown={handleSidebarKeyDown}
        onPointerEnter={openSidebar}
        onPointerLeave={scheduleSidebarClose}
      >
        <div className="app-brand">
          <img src={tothLogo} alt="TOTH" />
        </div>
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
            className={`block-nav-item${active === "catalogGenerator" ? " is-active" : ""}`}
            type="button"
            onClick={() => onChange("catalogGenerator")}
          >
            <span className="block-nav-number">07</span>
            <FileSpreadsheet size={18} aria-hidden="true" />
            <span className="block-nav-copy">
              <strong>Bloco 7</strong>
              <small>Gerador de catálogo</small>
            </span>
          </button>
        </nav>
        <div className="sidebar-context">Licitações públicas</div>
      </aside>
    </>
  );
}
