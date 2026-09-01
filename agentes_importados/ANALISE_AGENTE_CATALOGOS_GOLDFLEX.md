# Análise funcional - Agentes de Catálogos Goldflex

## Pacote analisado

- Origem: `agente-catalogos-goldflex-interno-v1-2026-08-20 (1).zip`
- Extração: `agentes_importados/agente-catalogos-goldflex-interno-v1-2026-08-20`
- Conteúdo: 238 entradas no ZIP, 197 arquivos extraídos e aproximadamente 36 MB.
- Nenhum arquivo do pacote foi executado durante a análise.

## Funcionalidades previstas

O pacote define um pipeline editorial com sete papéis:

1. **Analista visual:** avalia layout, hierarquia, imagens, tabelas e legibilidade.
2. **Classificador de produto:** identifica família, subfamília e variante sem transformar hipótese em fato.
3. **Extrator técnico:** extrai medidas, materiais, componentes, mecanismos, normas e demais campos com fonte.
4. **Normalizador:** consolida os dados nos níveis básico, intermediário e completo.
5. **Criador de catálogo:** redige um novo catálogo a partir de evidências e de um modelo aprovado.
6. **Revisor final:** compara conteúdo técnico e padrão visual, emitindo aprovação, pendências ou reprovação.
7. **Agente editorial:** transforma os dados aprovados em um DOCX Goldflex baseado no padrão V4.

Estados de evidência previstos: confirmado, indicado visualmente, não comprovado, ausente, a confirmar e conflitante.

## Ativos disponíveis

- 47 PDFs de referência.
- 43 documentos DOCX.
- 70 documentos Markdown com laudos, comparações e regras.
- 19 scripts Python e um script JavaScript.
- Schema YAML para relatório estruturado.
- Configuração JSON do modelo editorial aprovado.
- Templates de ficha de produto e revisão final.
- Biblioteca inicial de modelos de cadeiras e registros comparativos.

## Estado real da automação

Os sete agentes ainda são especificações em Markdown. O pacote não possui um orquestrador que carregue os prompts, execute as etapas, valide o schema e transporte o resultado entre agentes.

Os scripts existentes são geradores e consolidadores específicos. A maioria executa diretamente ao ser iniciada, usa caminhos relativos ou históricos e não oferece uma API reutilizável. Não existem testes automatizados, arquivo de dependências ou comando único de instalação.

## Pontos fortes

- Regra consistente contra invenção de especificações.
- Rastreabilidade por arquivo, página e região.
- Separação entre catálogo, laudo, confirmação do fabricante e edital.
- Estados explícitos para ausência, conflito e pendência.
- Regra de comparação dimensional com diferença absoluta e percentual.
- Modelo editorial V4 e fabricante padrão definidos.
- Acervo documental suficiente para iniciar uma biblioteca técnica de cadeiras.

## Riscos e inconsistências

1. Alguns geradores antigos contradizem as regras atuais: usam fabricante histórico, catálogo específico para pedido e seções hoje proibidas.
2. O validador verifica apenas arquivos V2 e somente procura termos genéricos; ele não valida o padrão V4 nem as regras editoriais atuais.
3. Alguns scripts possuem caminhos absolutos de outro usuário (`C:\Users\marcs\...`).
4. O manifesto menciona uma pasta `scripts/`, mas os scripts estão na raiz.
5. O schema YAML é um modelo de dados, não um schema formal validável.
6. O pacote não declara versões de Python, Node ou bibliotecas.
7. Há quatro grupos de arquivos binários duplicados.
8. Alguns nomes com acentos foram corrompidos no ZIP, quebrando caminhos referenciados como `validação de dados`.
9. Os documentos podem conter dados de processos, contatos e órgãos; o pacote deve permanecer interno.
10. Os DOCX V3 e V4 do Mocho Estância Velha são binariamente idênticos; a mudança de versão não representa uma revisão material do arquivo.
11. O DOCX indicado como V4 ainda menciona uma configuração destinada à Prefeitura de Estância Velha e apresenta o fabricante sem o CNPJ obrigatório, contrariando parcialmente as regras atuais de catálogo genérico e identificação institucional.

## Integração recomendada com o Toth

O Bloco de Catálogos atual já cobre cadastro, carregamento pelo PNCP, imagens, pré-visualização, alertas e exportação. A integração deve acrescentar um serviço de pipeline, sem executar diretamente os geradores históricos.

Fluxo recomendado:

```text
Item/Edital + PDFs + imagens
        -> inventário e extração
        -> classificação do produto
        -> normalização com evidências
        -> comparação de medidas
        -> rascunho editorial
        -> revisão técnica e visual
        -> aprovação humana
        -> exportação DOCX/PDF/JSON
```

Cada etapa deve receber e devolver JSON validado, com `status`, `fonte`, `página`, `região`, `confiança`, `conflitos` e `pendências`. O modelo V4 deve ser preservado como arquivo somente leitura, e cada geração deve produzir uma nova versão.

## Conclusão

O pacote é uma boa base de conhecimento e governança editorial, mas ainda não é um conjunto de agentes executáveis. Para uso seguro no Toth, os prompts, regras, schema e biblioteca devem ser incorporados a um novo orquestrador; os scripts históricos devem servir apenas como referência até serem parametrizados, testados e alinhados integralmente ao padrão V4.
