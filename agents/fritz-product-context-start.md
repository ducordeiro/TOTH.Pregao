---
name: fritz-product-context-start
description: Carrega contexto completo de um produto Fritz antes de qualquer operacao
---

# fritz-product-context-start

Skill utilitaria que carrega o contexto completo de um produto Fritz antes de qualquer operacao.
Todo agente deve executar esta skill como primeiro passo.

## O que esta skill faz

1. Identifica o produto-alvo pelo diretorio de trabalho atual
2. Carrega meta/product-map.yaml e localiza o produto
3. Valida que o produto esta ativo (nao deprecated)
4. Carrega o CLAUDE.md do produto
5. Carrega o AGENTS.md do produto (se existir)
6. Identifica a stack do produto (banco, packaging, ports)
7. Resume o contexto em formato estruturado

## Output esperado

```
PRODUTO: [nome]
STATUS: [active|paused|deprecated]
TIPO: [product|tenant-variant|devtool]
DOMINIO: [descricao]
DATABASE: [postgresql-16|sqlite|filesystem]
PACKAGING: [web-only|tauri|electron]
PORT_API: [numero]
PORT_WEB: [numero]
REPO: [nome do repositorio]
BASELINE: [produto base, se tenant-variant]

STACK:
  Frontend: React 19 + Vite + TypeScript
  Backend: Fastify 5 + Drizzle + [database]
  Styling: Tailwind v4 + shadcn/ui
  Testing: Vitest
  Linting: Biome

REGRAS ESPECIFICAS:
  [regras do CLAUDE.md do produto]

PROXIMO PASSO:
  Executar fritz-skill-router para determinar o agente adequado.
```

## Regras

- SEMPRE execute antes de qualquer outro skill ou agente
- NUNCA prossiga se o produto estiver deprecated
- SE o produto nao existir em product-map.yaml, informar e perguntar ao usuario
- SE o produto for tenant-variant, carregar contexto do baseline tambem
