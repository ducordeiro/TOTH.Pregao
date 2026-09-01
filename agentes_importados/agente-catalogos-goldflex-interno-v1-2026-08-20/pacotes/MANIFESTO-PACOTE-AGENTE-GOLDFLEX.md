# Manifesto do pacote interno — Agente de Catálogos Goldflex

## Finalidade

Este pacote reúne o repertório técnico e editorial usado pelo agente de catálogos Goldflex.

## Conteúdo

- `AGENTS.md`: regras permanentes do projeto.
- `README.md`: visão geral da arquitetura.
- `config/`: regras estruturadas e identificação do modelo aprovado.
- `docs/`: fluxo e arquitetura editorial.
- `prompts/`: papéis dos agentes de análise, normalização, criação e revisão.
- `schemas/`: estrutura normalizada dos relatórios.
- `templates/`: modelos auxiliares.
- `scripts/`: automações de geração, consolidação e validação.
- `analises/`: registros estruturados existentes.
- `Modelos de catalogos/catalogos de pedidos/`: PDFs, laudos, relatórios e documentos de referência.
- `Modelos de catalogos/validação de dados/`: biblioteca consolidada e validações de modelos.

## Modelo editorial

O padrão oficial é a versão 4, identificado no `AGENTS.md` e em `config/modelo-aprovado-goldflex.json`.

## Aviso de compartilhamento

Este é um pacote interno completo. Os catálogos históricos podem conter dados de processos, órgãos públicos, contatos, endereços e outras informações presentes nos documentos originais. Antes de distribuição externa, revisar quais arquivos estão autorizados para compartilhamento.

## Instalação e uso

Descompacte mantendo a estrutura de pastas. Abra a pasta raiz como projeto no Codex. O agente deve ler `AGENTS.md` antes de atuar e consultar os laudos e catálogos específicos do modelo solicitado.
