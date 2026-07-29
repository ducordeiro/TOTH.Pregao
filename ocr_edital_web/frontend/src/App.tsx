import { useCallback, useEffect, useState } from "react";
import { listResponsibles, listTemplates } from "./api";
import { CatalogBlock } from "./components/CatalogBlock";
import { BusinessBlock } from "./components/BusinessBlock";
import { ProposalBlock } from "./components/ProposalBlock";
import { ProjectStructureBlock } from "./components/ProjectStructureBlock";
import { ResponsibleManagerModal } from "./components/ResponsibleManagerModal";
import { SearchBlock } from "./components/SearchBlock";
import { Sidebar, type ActiveBlock } from "./components/Sidebar";
import { TemplateManagerModal } from "./components/TemplateManagerModal";
import type { Responsible, Template, UiMessage } from "./types";

export default function App() {
  const [activeBlock, setActiveBlock] = useState<ActiveBlock>("search");
  const [pncpLink, setPncpLink] = useState("");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [responsibles, setResponsibles] = useState<Responsible[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedResponsibleId, setSelectedResponsibleId] = useState("");
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [responsibleModalOpen, setResponsibleModalOpen] = useState(false);
  const [catalogMessage, setCatalogMessage] = useState<UiMessage | null>(null);

  const applyTemplates = useCallback(
    (updated: Template[], preferredId = "") => {
      setTemplates(updated);
      setSelectedTemplateId((current) => {
        const desired = preferredId || current;
        return updated.some((template) => template.id === desired)
          ? desired
          : updated[0]?.id || "";
      });
    },
    [],
  );

  const applyResponsibles = useCallback(
    (updated: Responsible[], preferredId = "") => {
      setResponsibles(updated);
      setSelectedResponsibleId((current) => {
        const desired = preferredId || current;
        return updated.some((responsible) => responsible.id === desired)
          ? desired
          : updated[0]?.id || "";
      });
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([listTemplates(), listResponsibles()])
      .then(([templateData, responsibleData]) => {
        if (cancelled) return;
        applyTemplates(templateData);
        applyResponsibles(responsibleData);
      })
      .catch((error) => {
        if (cancelled) return;
        setCatalogMessage({
          kind: "error",
          text: error instanceof Error
            ? error.message
            : "Não foi possível carregar os dados iniciais.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [applyResponsibles, applyTemplates]);

  const selectBlock = (block: ActiveBlock) => {
    setActiveBlock(block);
    window.requestAnimationFrame(() => {
      const workspaceId = {
        search: "search-workspace",
        proposal: "proposal-workspace",
        catalog: "catalog-workspace",
        business: "business-workspace",
        structure: "structure-workspace",
      }[block];
      document.getElementById(workspaceId)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const headerByBlock: Record<ActiveBlock, {
    eyebrow: string;
    title: string;
    description: string;
  }> = {
    search: {
      eyebrow: "Oportunidades públicas",
      title: "Buscar oportunidades",
      description: "Consulte editais disponíveis no PNCP e localize oportunidades.",
    },
    proposal: {
      eyebrow: "Propostas comerciais",
      title: "Gerar proposta",
      description: "Consulte o edital, selecione os itens e gere o documento Word.",
    },
    catalog: {
      eyebrow: "Documentos técnicos",
      title: "Catálogo técnico",
      description: "Estruture os dados do produto e gere os arquivos da licitação.",
    },
    business: {
      eyebrow: "Gestão comercial",
      title: "Negócios",
      description: "Acompanhe oportunidades e decisões em cada etapa da licitação.",
    },
    structure: {
      eyebrow: "Estrutura operacional",
      title: "Estrutura do projeto",
      description: "Organize etapas, responsáveis e entregáveis antes da entrega final.",
    },
  };
  const header = headerByBlock[activeBlock];

  return (
    <div className={`app-shell is-${activeBlock}-active`}>
      <Sidebar active={activeBlock} onChange={selectBlock} />
      <div className="app-content">
        <header className="app-header">
          <div className="header-spacer" />
          <div className="header-copy">
            <span>{header.eyebrow}</span>
            <h1>{header.title}</h1>
            <p>{header.description}</p>
          </div>
          <div className="catalog-status">
            {catalogMessage
              ? catalogMessage.text
              : `${templates.length} template(s) · ${responsibles.length} responsável(is)`}
          </div>
        </header>

        <main>
          <div id="search-workspace" hidden={activeBlock !== "search"}>
            <SearchBlock
              onUseLink={(link) => {
                setPncpLink(link);
                selectBlock("proposal");
              }}
            />
          </div>
          <div id="proposal-workspace" hidden={activeBlock !== "proposal"}>
            <ProposalBlock
              pncpLink={pncpLink}
              onPncpLinkChange={setPncpLink}
              templates={templates}
              responsibles={responsibles}
              selectedTemplateId={selectedTemplateId}
              selectedResponsibleId={selectedResponsibleId}
              onSelectedTemplateChange={setSelectedTemplateId}
              onSelectedResponsibleChange={setSelectedResponsibleId}
              onOpenTemplates={() => setTemplateModalOpen(true)}
              onOpenResponsibles={() => setResponsibleModalOpen(true)}
            />
          </div>
          <div id="catalog-workspace" hidden={activeBlock !== "catalog"}>
            <CatalogBlock
              pncpLink={pncpLink}
              onPncpLinkChange={setPncpLink}
            />
          </div>
          <div id="business-workspace" hidden={activeBlock !== "business"}>
            <BusinessBlock responsibles={responsibles} />
          </div>
          <div id="structure-workspace" hidden={activeBlock !== "structure"}>
            <ProjectStructureBlock />
          </div>
        </main>
      </div>

      <TemplateManagerModal
        open={templateModalOpen}
        templates={templates}
        selectedId={selectedTemplateId}
        onClose={() => setTemplateModalOpen(false)}
        onTemplatesChange={applyTemplates}
      />
      <ResponsibleManagerModal
        open={responsibleModalOpen}
        responsibles={responsibles}
        selectedId={selectedResponsibleId}
        onClose={() => setResponsibleModalOpen(false)}
        onResponsiblesChange={applyResponsibles}
        onSelect={setSelectedResponsibleId}
      />
    </div>
  );
}
