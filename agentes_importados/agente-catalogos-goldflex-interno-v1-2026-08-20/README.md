# Arquitetura de avaliação e criação de catálogos técnicos

Estrutura reutilizável para avaliar catálogos em PDF e orientar a criação/revisão de novos catálogos. O foco inicial é mobiliário corporativo, especialmente cadeiras de escritório, sem preencher especificações não comprovadas.

## Como usar

1. Coloque o PDF e, se existir, a ficha técnica/referência aprovada em uma pasta de trabalho do caso.
2. Siga [`docs/fluxo-operacional.md`](docs/fluxo-operacional.md), registrando evidências por página e região.
3. Use os prompts em [`prompts/`](prompts/) na ordem indicada.
4. Preencha [`schemas/relatorio-catalogo.yaml`](schemas/relatorio-catalogo.yaml) ou os modelos em [`templates/`](templates/).
5. Antes de aprovar, execute a revisão visual e técnica e liste toda pendência em vez de inferir.

## Editoração de modelos aprovados

Para criar novas versões dos catálogos Word, use [`docs/arquitetura-agente-editorial-catalogo.md`](docs/arquitetura-agente-editorial-catalogo.md), o prompt [`prompts/07-agente-editorial-catalogo.md`](prompts/07-agente-editorial-catalogo.md) e as regras [`config/modelo-aprovado-goldflex.json`](config/modelo-aprovado-goldflex.json). A validação estrutural dos DOCX é executada por `validar_catalogo_editorial.py`.

## Regra central

Cada afirmação técnica deve apontar para uma evidência observável (página, bloco/tabela, texto ou imagem) ou ser marcada como `não comprovado`, `ausente` ou `a confirmar`. Exemplos de produtos são hipotéticos e não devem ser tratados como dados reais.
