import { useRef, useState } from "react";
import { FilePlus2, RefreshCw, Trash2 } from "lucide-react";
import {
  createTemplate,
  deleteTemplate,
  listTemplates,
  replaceTemplate,
} from "../api";
import type { Template, UiMessage } from "../types";
import { formatFileSize, validateTemplateFile } from "../utils";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

interface TemplateManagerModalProps {
  open: boolean;
  templates: Template[];
  selectedId: string;
  onClose: () => void;
  onTemplatesChange: (templates: Template[], preferredId?: string) => void;
}

type PendingAction =
  | { type: "create" }
  | { type: "replace"; template: Template };

export function TemplateManagerModal({
  open,
  templates,
  selectedId,
  onClose,
  onTemplatesChange,
}: TemplateManagerModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);

  const chooseFile = (action: PendingAction) => {
    if (busy) return;
    setPending(action);
    if (inputRef.current) {
      inputRef.current.value = "";
      inputRef.current.click();
    }
  };

  const refresh = async (preferredId?: string) => {
    const updated = await listTemplates();
    onTemplatesChange(updated, preferredId);
  };

  const upload = async (file: File) => {
    const validationError = validateTemplateFile(file);
    if (validationError) {
      setMessage({ kind: "error", text: validationError });
      return;
    }
    const action = pending;
    setPending(null);
    if (!action) return;
    setBusy(true);
    setMessage({
      kind: "info",
      text: action.type === "replace" ? "Substituindo template..." : "Anexando template...",
    });
    try {
      const saved =
        action.type === "replace"
          ? await replaceTemplate(action.template.id, file)
          : await createTemplate(file);
      await refresh(saved.id);
      setMessage({
        kind: "success",
        text: action.type === "replace"
          ? "Template substituído com sucesso."
          : "Template anexado com sucesso.",
      });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível salvar o template.",
      });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (template: Template) => {
    if (busy || !window.confirm(`Excluir o template "${template.name}"?`)) return;
    setBusy(true);
    setMessage({ kind: "info", text: "Excluindo template..." });
    try {
      await deleteTemplate(template.id);
      await refresh();
      setMessage({ kind: "success", text: "Template excluído com sucesso." });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível excluir o template.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open={open} title="Templates" busy={busy} onClose={onClose}>
      <div className="modal-toolbar">
        <strong>Arquivos cadastrados</strong>
        <button
          className="button button-primary"
          type="button"
          disabled={busy}
          onClick={() => chooseFile({ type: "create" })}
        >
          <FilePlus2 size={17} />
          Anexar novo template
        </button>
      </div>
      <StatusMessage message={message} compact />
      <div className="manager-list">
        {templates.length ? (
          templates.map((template) => (
            <article
              className={`manager-row${template.id === selectedId ? " is-selected" : ""}`}
              key={template.id}
            >
              <div className="manager-details">
                <strong>{template.name}</strong>
                <span>{formatFileSize(template.size)}</span>
              </div>
              <div className="manager-actions">
                <button
                  className="button button-secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => chooseFile({ type: "replace", template })}
                >
                  <RefreshCw size={16} />
                  Substituir
                </button>
                <button
                  className="button button-danger"
                  type="button"
                  disabled={busy}
                  onClick={() => remove(template)}
                >
                  <Trash2 size={16} />
                  Excluir
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="empty-state">Nenhum template cadastrado.</div>
        )}
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) void upload(file);
          else setPending(null);
        }}
      />
    </Modal>
  );
}
