import { useEffect, useState } from "react";
import { Check, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createResponsible,
  deleteResponsible,
  listResponsibles,
  updateResponsible,
  type ResponsiblePayload,
} from "../api";
import type { Responsible, UiMessage } from "../types";
import { Modal } from "./Modal";
import { StatusMessage } from "./StatusMessage";

interface ResponsibleManagerModalProps {
  open: boolean;
  responsibles: Responsible[];
  selectedId: string;
  onClose: () => void;
  onResponsiblesChange: (responsibles: Responsible[], preferredId?: string) => void;
  onSelect: (id: string) => void;
}

const emptyForm: ResponsiblePayload = {
  nome_completo: "",
  empresa: "",
  cnpj: "",
  rg: "",
  cpf: "",
  observacoes: "",
};

export function ResponsibleManagerModal({
  open,
  responsibles,
  selectedId,
  onClose,
  onResponsiblesChange,
  onSelect,
}: ResponsibleManagerModalProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<ResponsiblePayload>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<UiMessage | null>(null);

  useEffect(() => {
    if (!open) {
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setMessage(null);
    }
  }, [open]);

  const refresh = async (preferredId?: string) => {
    const updated = await listResponsibles();
    onResponsiblesChange(updated, preferredId);
  };

  const beginCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setShowForm(true);
    setMessage(null);
  };

  const beginEdit = (responsible: Responsible) => {
    setEditingId(responsible.id);
    setForm({
      nome_completo: responsible.nome_completo,
      empresa: responsible.empresa,
      cnpj: responsible.cnpj,
      rg: responsible.rg,
      cpf: responsible.cpf,
      observacoes: responsible.observacoes,
    });
    setShowForm(true);
    setMessage(null);
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    const cnpjDigits = form.cnpj.replace(/\D/g, "");
    const cpfDigits = form.cpf.replace(/\D/g, "");
    if (cnpjDigits.length !== 14) {
      setMessage({ kind: "error", text: "Informe um CNPJ com 14 dígitos." });
      return;
    }
    if (form.cpf && cpfDigits.length !== 11) {
      setMessage({ kind: "error", text: "Informe um CPF com 11 dígitos." });
      return;
    }
    setBusy(true);
    setMessage({ kind: "info", text: editingId ? "Atualizando responsável..." : "Cadastrando responsável..." });
    try {
      const saved = editingId
        ? await updateResponsible(editingId, form)
        : await createResponsible(form);
      await refresh(saved.id);
      setShowForm(false);
      setEditingId(null);
      setForm(emptyForm);
      setMessage({
        kind: "success",
        text: editingId ? "Responsável atualizado com sucesso." : "Responsável cadastrado com sucesso.",
      });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível salvar o responsável.",
      });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (responsible: Responsible) => {
    if (busy || !window.confirm(`Excluir o responsável "${responsible.nome_completo}"?`)) return;
    setBusy(true);
    setMessage({ kind: "info", text: "Verificando vínculos e excluindo responsável..." });
    try {
      await deleteResponsible(responsible.id);
      await refresh();
      setMessage({ kind: "success", text: "Responsável excluído com sucesso." });
    } catch (error) {
      setMessage({
        kind: "error",
        text: error instanceof Error ? error.message : "Não foi possível excluir o responsável.",
      });
    } finally {
      setBusy(false);
    }
  };

  const updateField = (field: keyof ResponsiblePayload, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  return (
    <Modal open={open} title="Responsáveis" busy={busy} onClose={onClose} wide>
      <div className="modal-toolbar">
        <strong>Responsáveis cadastrados</strong>
        <button className="button button-primary" type="button" disabled={busy} onClick={beginCreate}>
          <Plus size={17} />
          Cadastrar responsável
        </button>
      </div>
      <StatusMessage message={message} compact />

      {showForm && (
        <form className="manager-form" onSubmit={save}>
          <h3>{editingId ? "Editar responsável" : "Novo responsável"}</h3>
          <div className="manager-form-grid">
            <label className="span-two">
              Nome completo *
              <input
                required
                maxLength={200}
                value={form.nome_completo}
                onChange={(e) => updateField("nome_completo", e.target.value)}
              />
            </label>
            <label className="span-two">
              Empresa *
              <input
                required
                maxLength={200}
                value={form.empresa}
                onChange={(e) => updateField("empresa", e.target.value)}
              />
            </label>
            <label>
              CNPJ *
              <input
                required
                maxLength={24}
                value={form.cnpj}
                placeholder="00.000.000/0000-00"
                onChange={(e) => updateField("cnpj", e.target.value)}
              />
            </label>
            <label>
              RG
              <input
                maxLength={30}
                value={form.rg}
                onChange={(e) => updateField("rg", e.target.value)}
              />
            </label>
            <label>
              CPF
              <input
                maxLength={20}
                value={form.cpf}
                placeholder="000.000.000-00"
                onChange={(e) => updateField("cpf", e.target.value)}
              />
            </label>
            <label className="span-two">
              Observações
              <textarea
                maxLength={1000}
                value={form.observacoes}
                onChange={(e) => updateField("observacoes", e.target.value)}
              />
            </label>
          </div>
          <div className="form-actions align-right">
            <button
              className="button button-secondary"
              type="button"
              disabled={busy}
              onClick={() => setShowForm(false)}
            >
              Cancelar
            </button>
            <button className="button button-primary" type="submit" disabled={busy}>
              {busy ? "Salvando..." : "Salvar responsável"}
            </button>
          </div>
        </form>
      )}

      <div className="manager-list">
        {responsibles.length ? (
          responsibles.map((responsible) => (
            <article
              className={`manager-row${responsible.id === selectedId ? " is-selected" : ""}`}
              key={responsible.id}
            >
              <div className="manager-details">
                <strong>{responsible.nome_completo}</strong>
                <span>
                  {responsible.empresa}
                  {responsible.cpf ? ` · CPF ${responsible.cpf}` : ""}
                </span>
              </div>
              <div className="manager-actions">
                <button
                  className="button button-primary"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    onSelect(responsible.id);
                    onClose();
                  }}
                >
                  <Check size={16} />
                  {responsible.id === selectedId ? "Selecionado" : "Selecionar"}
                </button>
                <button
                  className="button button-secondary"
                  type="button"
                  disabled={busy}
                  onClick={() => beginEdit(responsible)}
                >
                  <Pencil size={16} />
                  Editar
                </button>
                <button
                  className="button button-danger"
                  type="button"
                  disabled={busy}
                  onClick={() => remove(responsible)}
                >
                  <Trash2 size={16} />
                  Excluir
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="empty-state">Nenhum responsável cadastrado.</div>
        )}
      </div>
    </Modal>
  );
}
