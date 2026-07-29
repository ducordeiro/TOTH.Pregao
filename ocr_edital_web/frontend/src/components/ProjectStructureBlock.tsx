import { CheckCircle2, ClipboardList, Copy, RotateCcw } from "lucide-react";
import { useMemo, useState } from "react";
import type { UiMessage } from "../types";
import { StatusMessage } from "./StatusMessage";

const PHASES = [
  {
    id: "levantamento",
    title: "Levantamento",
    description: "Objeto, órgão, edital, datas e link oficial.",
  },
  {
    id: "analise",
    title: "Análise",
    description: "Requisitos técnicos, comerciais e documentação.",
  },
  {
    id: "composicao",
    title: "Composição",
    description: "Itens, marcas, valores, prazos e condições.",
  },
  {
    id: "revisao",
    title: "Revisão",
    description: "Conferência final da proposta e anexos.",
  },
  {
    id: "envio",
    title: "Envio",
    description: "Registro da entrega e acompanhamento do resultado.",
  },
] as const;

const DELIVERABLES = [
  "Proposta comercial",
  "Catálogo técnico",
  "Documentos de habilitação",
  "Planilha de itens e preços",
  "Comprovante de envio",
] as const;

const INITIAL_COMPLETED = new Set<string>(["levantamento"]);

export function ProjectStructureBlock() {
  const [projectName, setProjectName] = useState("");
  const [organization, setOrganization] = useState("");
  const [owner, setOwner] = useState("");
  const [internalDeadline, setInternalDeadline] = useState("");
  const [objective, setObjective] = useState("");
  const [notes, setNotes] = useState("");
  const [completedPhases, setCompletedPhases] = useState(INITIAL_COMPLETED);
  const [selectedDeliverables, setSelectedDeliverables] = useState(
    new Set<string>(["Proposta comercial", "Planilha de itens e preços"]),
  );
  const [message, setMessage] = useState<UiMessage | null>(null);

  const completedCount = completedPhases.size;
  const deliverablesCount = selectedDeliverables.size;
  const progress = Math.round((completedCount / PHASES.length) * 100);

  const summary = useMemo(() => {
    const phaseLines = PHASES.map((phase) => {
      const marker = completedPhases.has(phase.id) ? "concluído" : "pendente";
      return `- ${phase.title}: ${marker}`;
    }).join("\n");
    const deliverableLines = DELIVERABLES.filter((item) => selectedDeliverables.has(item))
      .map((item) => `- ${item}`)
      .join("\n");

    return [
      `Projeto: ${projectName || "Sem nome definido"}`,
      `Órgão/cliente: ${organization || "Não informado"}`,
      `Responsável: ${owner || "Não informado"}`,
      `Prazo interno: ${internalDeadline || "Não informado"}`,
      "",
      "Objetivo:",
      objective || "Não informado",
      "",
      "Etapas:",
      phaseLines,
      "",
      "Entregáveis:",
      deliverableLines || "- Nenhum entregável selecionado",
      "",
      "Observações:",
      notes || "Sem observações.",
    ].join("\n");
  }, [
    completedPhases,
    internalDeadline,
    notes,
    objective,
    organization,
    owner,
    projectName,
    selectedDeliverables,
  ]);

  const togglePhase = (phaseId: string) => {
    setCompletedPhases((current) => {
      const next = new Set(current);
      if (next.has(phaseId)) {
        next.delete(phaseId);
      } else {
        next.add(phaseId);
      }
      return next;
    });
    setMessage(null);
  };

  const toggleDeliverable = (deliverable: string) => {
    setSelectedDeliverables((current) => {
      const next = new Set(current);
      if (next.has(deliverable)) {
        next.delete(deliverable);
      } else {
        next.add(deliverable);
      }
      return next;
    });
    setMessage(null);
  };

  const reset = () => {
    setProjectName("");
    setOrganization("");
    setOwner("");
    setInternalDeadline("");
    setObjective("");
    setNotes("");
    setCompletedPhases(new Set(INITIAL_COMPLETED));
    setSelectedDeliverables(new Set(["Proposta comercial", "Planilha de itens e preços"]));
    setMessage({ kind: "info", text: "Estrutura reiniciada." });
  };

  const copySummary = async () => {
    try {
      await navigator.clipboard.writeText(summary);
      setMessage({ kind: "success", text: "Resumo da estrutura copiado." });
    } catch {
      setMessage({ kind: "error", text: "Não foi possível copiar o resumo." });
    }
  };

  return (
    <section className="workspace-section structure-workspace" aria-labelledby="structure-heading">
      <div className="section-heading">
        <div>
          <span className="section-kicker">Bloco 5</span>
          <h2 id="structure-heading">Estrutura do projeto</h2>
          <p>Organize a base operacional da licitação antes da montagem final.</p>
        </div>
        <div className="structure-heading-actions">
          <button className="button button-secondary" type="button" onClick={reset}>
            <RotateCcw size={16} aria-hidden="true" />
            Limpar
          </button>
          <button className="button button-primary" type="button" onClick={copySummary}>
            <Copy size={16} aria-hidden="true" />
            Copiar
          </button>
        </div>
      </div>

      {message && <StatusMessage message={message} />}

      <div className="structure-grid">
        <form className="structure-form">
          <label>
            Nome do projeto
            <input
              value={projectName}
              onChange={(event) => setProjectName(event.target.value)}
              placeholder="Ex.: Pregão mobiliário escolar"
            />
          </label>
          <label>
            Órgão ou cliente
            <input
              value={organization}
              onChange={(event) => setOrganization(event.target.value)}
              placeholder="Ex.: Prefeitura Municipal"
            />
          </label>
          <label>
            Responsável interno
            <input
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
              placeholder="Nome do responsável"
            />
          </label>
          <label>
            Prazo interno
            <input
              type="date"
              value={internalDeadline}
              onChange={(event) => setInternalDeadline(event.target.value)}
            />
          </label>
          <label className="span-two">
            Objetivo
            <textarea
              value={objective}
              onChange={(event) => setObjective(event.target.value)}
              placeholder="Objeto, escopo e critérios principais do projeto."
            />
          </label>
          <label className="span-two">
            Observações
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Pendências, riscos, decisões e pontos de atenção."
            />
          </label>
        </form>

        <aside className="structure-panel" aria-label="Resumo do bloco 5">
          <ClipboardList size={22} aria-hidden="true" />
          <strong>{progress}% estruturado</strong>
          <span>{completedCount}/{PHASES.length} etapas concluídas</span>
          <span>{deliverablesCount} entregável(is) selecionado(s)</span>
          <div className="structure-progress-track">
            <span style={{ width: `${progress}%` }} />
          </div>
        </aside>
      </div>

      <div className="structure-board">
        <div>
          <h3>Etapas</h3>
          <div className="structure-step-list">
            {PHASES.map((phase, index) => {
              const checked = completedPhases.has(phase.id);
              return (
                <label
                  className={`structure-step${checked ? " is-complete" : ""}`}
                  key={phase.id}
                >
                  <input
                    checked={checked}
                    type="checkbox"
                    onChange={() => togglePhase(phase.id)}
                  />
                  <span className="structure-step-number">{String(index + 1).padStart(2, "0")}</span>
                  <span>
                    <strong>{phase.title}</strong>
                    <small>{phase.description}</small>
                  </span>
                  {checked && <CheckCircle2 size={17} aria-hidden="true" />}
                </label>
              );
            })}
          </div>
        </div>

        <div>
          <h3>Entregáveis</h3>
          <div className="structure-deliverables">
            {DELIVERABLES.map((deliverable) => (
              <label key={deliverable}>
                <input
                  checked={selectedDeliverables.has(deliverable)}
                  type="checkbox"
                  onChange={() => toggleDeliverable(deliverable)}
                />
                <span>{deliverable}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
