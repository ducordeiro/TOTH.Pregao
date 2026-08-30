import { FileText } from "lucide-react";
import { createReplicaDocumentBlocks } from "../docxOrder";
import type {
  CommercialTerms,
  DocumentNode,
  GeneratedTableBlock,
  MiniBoxTextAlign,
  ProposalItem,
  Responsible,
} from "../types";
import { formatCents, parseMoneyToCents } from "../utils";

interface ProposalLivePreviewProps {
  nodes: DocumentNode[];
  blockOrder: string[];
  generatedTable: GeneratedTableBlock;
  items: ProposalItem[];
  commercialTerms: CommercialTerms;
  responsible?: Responsible;
  miniBoxAlignments: Record<string, MiniBoxTextAlign>;
}

function proposalTotal(items: ProposalItem[]): string {
  const cents = items.reduce((total, item) => {
    const itemCents = parseMoneyToCents(item.valor_total || "");
    return total + (itemCents || 0n);
  }, 0n);
  return formatCents(cents);
}

function ReplicaTable({ items }: { items: ProposalItem[] }) {
  const showLot = items.some((item) => Boolean(item.lote));
  return (
    <div className="proposal-replica-table-wrap">
      <table className="proposal-replica-table">
        <thead>
          <tr>
            {showLot && <th>LOTE</th>}
            <th>ITEM</th>
            <th>QTD</th>
            <th>UND</th>
            <th>DESCRIÇÃO</th>
            <th>MARCA</th>
            <th>VALOR UNITÁRIO</th>
            <th>VALOR TOTAL</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.lote || ""}-${item.item}`}>
              {showLot && <td>{item.lote}</td>}
              <td>{item.item}</td>
              <td>{item.quantidade}</td>
              <td>UND</td>
              <td className="proposal-replica-description">{item.descricao}</td>
              <td>{item.marca}</td>
              <td>{item.valor_unitario}</td>
              <td>{item.valor_total}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProposalLivePreview({
  nodes,
  blockOrder,
  generatedTable,
  items,
  commercialTerms,
  responsible,
  miniBoxAlignments,
}: ProposalLivePreviewProps) {
  const blocks = createReplicaDocumentBlocks(nodes, blockOrder, generatedTable);
  return (
    <section className="proposal-live-preview" aria-label="Pré-visualização simultânea da proposta">
      <div className="proposal-replica-toolbar">
        <FileText size={14} aria-hidden="true" />
        <span>Prévia da proposta</span>
      </div>
      <div className="proposal-replica-viewport">
        <article className="proposal-replica-page">
          {blocks.map((block, index) => {
            if (block.type === "GENERATED_TABLE") {
              return <ReplicaTable items={items} key={block.id} />;
            }
            const content = block.content.trim();
            if (!content) return null;
            return block.type === "MINI_BOX" ? (
              <section
                className="proposal-replica-mini-box"
                key={`${block.id}-${index}`}
                style={{ textAlign: miniBoxAlignments[block.id] || block.text_align }}
              >
                {content}
              </section>
            ) : (
              <p className="proposal-replica-fixed-text" key={`${block.id}-${index}`}>
                {content}
              </p>
            );
          })}
          <div className="proposal-replica-terms">
            <p><strong>VALOR TOTAL DA PROPOSTA:</strong> {proposalTotal(items)}</p>
            <p><strong>Prazo de Entrega:</strong> {commercialTerms.prazo_entrega}</p>
            <p><strong>Prazo de pagamento:</strong> {commercialTerms.prazo_pagamento}</p>
            <p><strong>Validade da Proposta:</strong> {commercialTerms.validade_proposta}</p>
          </div>
          {responsible && (
            <div className="proposal-replica-responsible">
              {responsible.empresa && <p>{responsible.empresa}</p>}
              <p>{responsible.nome_completo}</p>
              {responsible.rg && <p>RG {responsible.rg}</p>}
              {responsible.cpf && <p>CPF {responsible.cpf}</p>}
            </div>
          )}
        </article>
      </div>
    </section>
  );
}
