---
name: fritz-skill-router
description: Roteia demandas do usuario para o agente Fritz correto baseado no tipo de trabalho
---

# fritz-skill-router

Skill utilitaria que roteia a demanda do usuario para o agente Fritz correto.
Deve ser executada apos fritz-product-context-start.

## Logica de roteamento

Analisar a demanda do usuario e classificar:

### Palavras-chave → Agente

| Palavras-chave na demanda | Agente |
|---------------------------|--------|
| "novo app", "criar produto", "novo sistema" | fritz-product-planner |
| "planejar", "especificar", "definir entidades" | fritz-product-planner |
| "arquitetura", "stack", "PostgreSQL vs SQLite", "Tauri vs Electron" | fritz-architect |
| "gerar do template", "scaffolding", "criar estrutura" | fritz-scaffolder |
| "tela", "pagina", "componente", "UI", "layout", "visual" | fritz-frontend-builder |
| "API", "endpoint", "rota", "service", "backend" | fritz-backend-builder |
| "revisar", "review", "auditar", "qualidade" | fritz-reviewer |
| "banco", "schema", "normalizar", "indice", "query", "ERD" | fritz-db-analyst |
| "build", "release", "instalar", "deploy", "CI/CD" | fritz-release-ops |
| "shell", "sidebar", "loader", "toolbar", "design system" | fritz-ui-guardian |
| "tema", "cores", "paleta", "tokens", "dark mode" | fritz-theme-enforcer |
| "componente padrao", "biblioteca", "catalogo" | fritz-component-librarian |

### Demandas compostas

Se a demanda envolve multiplos agentes:
1. Identificar o agente primario (o que deve agir primeiro)
2. Identificar agentes secundarios (dependem do output do primario)
3. Definir sequencia de execucao
4. Passar para fritz-orchestrator coordenar

## Output

```
ROTEAMENTO:
  Agente primario: [nome]
  Agentes secundarios: [lista]
  Sequencia: [1 → 2 → 3]
  Justificativa: [porque este roteamento]
```

## Regras

- SEMPRE execute apos fritz-product-context-start
- NUNCA rotear para agente sem contexto de produto carregado
- SE a demanda for ambigua, perguntar ao usuario antes de rotear
- SE nenhum agente se encaixar, rotear para fritz-orchestrator
