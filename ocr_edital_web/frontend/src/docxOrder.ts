import type {
  DocumentNode,
  GeneratedTableBlock,
  MiniBoxNode,
} from "./types";

export type ReplicaDocumentBlock = DocumentNode | GeneratedTableBlock;

export function miniBoxNodes(nodes: DocumentNode[]): MiniBoxNode[] {
  return nodes
    .filter((node): node is MiniBoxNode => node.type === "MINI_BOX")
    .sort((left, right) => left.order - right.order);
}

export function miniBoxOrder(nodes: DocumentNode[]): string[] {
  return miniBoxNodes(nodes).map((node) => node.id);
}

export function createDocumentBlockOrder(
  nodes: DocumentNode[],
  generatedTableId: string,
): string[] {
  return [...miniBoxOrder(nodes), generatedTableId];
}

export function miniBoxOrderFromDocumentOrder(
  order: string[],
  generatedTableId: string,
): string[] {
  return order.filter((nodeId) => nodeId !== generatedTableId);
}

export function createReplicaDocumentBlocks(
  nodes: DocumentNode[],
  documentOrder: string[],
  generatedTable: GeneratedTableBlock,
): ReplicaDocumentBlock[] {
  const originalMiniBoxes = miniBoxNodes(nodes);
  const expectedIds = originalMiniBoxes.map((node) => node.id);
  const expectedOrder = [...expectedIds, generatedTable.id];
  const hasValidOrder = documentOrder.length === expectedOrder.length
    && new Set(documentOrder).size === documentOrder.length
    && expectedOrder.every((nodeId) => documentOrder.includes(nodeId));
  const resolvedOrder = hasValidOrder ? documentOrder : expectedOrder;
  const miniBoxesById = new Map(originalMiniBoxes.map((node) => [node.id, node]));
  const orderedMiniBoxes = resolvedOrder
    .filter((nodeId) => nodeId !== generatedTable.id)
    .map((nodeId) => miniBoxesById.get(nodeId))
    .filter((node): node is MiniBoxNode => Boolean(node));
  const tablePosition = resolvedOrder.indexOf(generatedTable.id);
  const replica: ReplicaDocumentBlock[] = [];
  let miniBoxSlot = 0;
  let tableInserted = false;

  for (const node of nodes) {
    if (node.type === "FIXED_TEXT") {
      replica.push(node);
      continue;
    }
    if (!tableInserted && miniBoxSlot === tablePosition) {
      replica.push(generatedTable);
      tableInserted = true;
    }
    replica.push(orderedMiniBoxes[miniBoxSlot] || node);
    miniBoxSlot += 1;
  }
  if (!tableInserted) replica.push(generatedTable);
  return replica;
}

export function applyMiniBoxOrder(
  nodes: DocumentNode[],
  orderedIds: string[],
): DocumentNode[] {
  const expectedIds = miniBoxOrder(nodes);
  if (
    orderedIds.length !== expectedIds.length
    || new Set(orderedIds).size !== orderedIds.length
    || orderedIds.some((nodeId) => !expectedIds.includes(nodeId))
  ) {
    return nodes;
  }
  const orders = new Map(orderedIds.map((nodeId, order) => [nodeId, order]));
  return nodes.map((node) =>
    node.type === "MINI_BOX"
      ? { ...node, order: orders.get(node.id) ?? node.order }
      : node,
  );
}

export function reorderDocumentBlocks(
  order: string[],
  activeId: string,
  overId: string,
): string[] {
  if (activeId === overId) return order;
  const oldIndex = order.indexOf(activeId);
  const newIndex = order.indexOf(overId);
  if (oldIndex < 0 || newIndex < 0) return order;
  const reordered = [...order];
  const [active] = reordered.splice(oldIndex, 1);
  reordered.splice(newIndex, 0, active);
  return reordered;
}

export function moveDocumentBlock(
  order: string[],
  nodeId: string,
  direction: -1 | 1,
): string[] {
  const currentIndex = order.indexOf(nodeId);
  const targetId = order[currentIndex + direction];
  if (currentIndex < 0 || !targetId) return order;
  return reorderDocumentBlocks(order, nodeId, targetId);
}

export function insertDocumentBlockBefore(
  order: string[],
  nodeId: string,
  beforeId?: string,
): string[] {
  const withoutNode = order.filter((candidateId) => candidateId !== nodeId);
  if (!beforeId) return [...withoutNode, nodeId];
  const targetIndex = withoutNode.indexOf(beforeId);
  if (targetIndex < 0) return [...withoutNode, nodeId];
  const inserted = [...withoutNode];
  inserted.splice(targetIndex, 0, nodeId);
  return inserted;
}

export function reorderMiniBoxes(
  nodes: DocumentNode[],
  activeId: string,
  overId: string,
): DocumentNode[] {
  if (activeId === overId) return nodes;
  const ordered = miniBoxNodes(nodes);
  const oldIndex = ordered.findIndex((node) => node.id === activeId);
  const newIndex = ordered.findIndex((node) => node.id === overId);
  if (oldIndex < 0 || newIndex < 0) return nodes;

  const moved = [...ordered];
  const [active] = moved.splice(oldIndex, 1);
  moved.splice(newIndex, 0, active);
  return applyMiniBoxOrder(nodes, moved.map((node) => node.id));
}

export function moveMiniBox(
  nodes: DocumentNode[],
  nodeId: string,
  direction: -1 | 1,
): DocumentNode[] {
  const ordered = miniBoxNodes(nodes);
  const currentIndex = ordered.findIndex((node) => node.id === nodeId);
  const target = ordered[currentIndex + direction];
  if (currentIndex < 0 || !target) return nodes;
  return reorderMiniBoxes(nodes, nodeId, target.id);
}
