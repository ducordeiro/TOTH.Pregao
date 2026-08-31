# Auditoria tecnica: blocos 1, 2, 4 e 7

Data: 31/08/2026. Aplicacao principal: http://127.0.0.1:8765/.

## Reteste apos as correcoes

**Aprovado nos sete criterios de regressao reproduzidos nesta auditoria.** O
reteste isolado concluiu 16 de 16 verificacoes, e os cenarios concorrentes foram
repetidos no navegador sem erros de console. Foram corrigidos:

- descarte de respostas do Bloco 2 pertencentes a edital ou revisao anterior;
- nomes unicos e imutabilidade das exportacoes Word;
- revalidacao dos campos obrigatorios editados no Bloco 7;
- consulta remota de arquivos fora do lock global do SQLite, com cache curto;
- paginacao local disponivel durante a verificacao online do Bloco 1;
- invalidacao de exports do Bloco 7 apos qualquer edicao;
- PDF sem corte de descricoes longas, com quebra entre paginas.

Foram aprovados 207 testes Python, 27 testes frontend, typecheck e build de
producao. Na medicao final, as medianas foram 154 ms para busca ampla, 67 ms
para `cadeira`, 162 ms para a pagina 2, 16 ms para 90 itens locais, 19 ms para
detalhe de oportunidade e 17 ms para detalhe de negocio ja consultado.

O servidor principal foi reiniciado na porta 8765 com a versao corrigida. A
cobertura de itens da base continua sendo uma limitacao de dados, separada das
sete falhas funcionais corrigidas.

## Conclusao executiva inicial

**Nao aprovado como livre de falhas e gargalos.** O fluxo nominal funciona nos
cenarios examinados, mas foram reproduzidas sete falhas, incluindo risco de
gerar proposta do edital anterior e de sobrescrever um documento ja gerado.
A cobertura de itens tambem continua insuficiente para busca abrangente por produto.

Esta entrega e uma auditoria, nao uma alteracao das regras de negocio. Foram
adicionados o executor de auditoria e as evidencias; as falhas abaixo permanecem
pendentes. Nenhum negocio real foi criado, editado, arquivado ou removido.
As alteracoes anteriores do projeto foram preservadas. Nao houve commit/push.

## Metodo e protecao dos dados

- Revisao estatica dos componentes React, contratos HTTP, persistencia SQLite,
  tratamento de erros, estado assincrono e geracao de arquivos.
- 203 testes Python existentes aprovados; 27 testes frontend existentes aprovados.
- Typecheck aprovado. Build de producao verificado ao final.
- 16 verificacoes adicionais em HTTP/banco isolados: **12 aprovadas e 4 falhas**.
- Testes no navegador com a mesma build do app e base temporaria com 24
  oportunidades ficticias, dois itens por oportunidade. Tres falhas adicionais
  foram reproduzidas na interface.
- Atrasos de 4 s no processamento e 1 s na resposta online foram injetados apenas
  no servidor temporario para testar respostas fora de ordem e disponibilidade.
- Na aplicacao principal foram feitas leituras HTTP, contagens SQLite em modo
  somente leitura e um processamento de catalogo de um item, sem exportacao.
  Leituras de detalhe podem acionar o enriquecimento/cache normal do app.
- Nenhuma carga massiva, coleta historica, exclusao de dados, troca de template
  ou mudanca de configuracao do servidor principal foi executada.

## Falhas reproduzidas

### F1. Alta: resposta antiga pode reaparecer na proposta de outro edital

**Bloco 2.** Iniciar o processamento do edital QA 001 e, antes de concluir,
trocar a URL para QA 002. A interface passa a mostrar a URL `/2026/2`, mas
restaura a proposta com `Cadeira estofada - edital QA 001`, permitindo gerar Word.

Causa: `process()` aplica a resposta e a estrutura sem conferir se link,
template e selecao continuam correspondendo a requisicao original. O reset
do estado ao trocar a URL nao invalida as promessas em andamento. `generate()`
tambem nao verifica a revisao atual antes de publicar o download.

Referencia: [ProposalBlock.tsx:280](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/frontend/src/components/ProposalBlock.tsx:280>).

Correcao recomendada: usar identificador de revisao da proposta, invalidado
por alteracoes de origem/template/dados; verificar essa revisao depois de
cada `await`, inclusive erros, estrutura e geracao. Cancelar leituras obsoletas
quando possivel. Nao publicar resultados de uma revisao antiga.

### F2. Alta: documentos Word podem sobrescrever uma exportacao anterior

**Bloco 2.** Duas geracoes com o mesmo `source_name` no mesmo segundo recebem
o mesmo nome de arquivo. No teste, o download da primeira proposta passou a
conter a segunda versao. O relogio do nome foi fixado somente no ambiente isolado.

Referencia: [server.py:11196](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/server.py:11196>).

Correcao recomendada: identificador unico por exportacao, escrita em arquivo
temporario e publicacao atomica, sem reutilizar o caminho de um download anterior.
Adicionar teste de duas geracoes concorrentes do mesmo edital.

### F3. Alta: campos obrigatorios editados nao sao revalidados no catalogo

**Bloco 7.** Apagar descricao e quantidade e exportar foi aceito com HTTP 200,
`incompletos: 0` e nenhum aviso. O servidor confia em `campos_ausentes` recebido
do cliente, que descreve a versao original, nao os valores revisados.

Referencia: [catalog_generator.py:110](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/catalog_generator.py:110>).

Correcao recomendada: validar os campos efetivos no backend na exportacao;
recalcular pendencias e evidencia apos cada revisao. Nao tratar uma lista de
avisos enviada pelo navegador como validacao confiavel.

### F4. Media: espera pelo PNCP bloqueia outras operacoes de banco

**Bloco 4 e servicos compartilhados.** `get_business(..., include_details=True)`
mantem `DATABASE_LOCK` enquanto `business_files()` pode consultar a rede.
Com 1.000 ms de atraso externo simulado, uma leitura independente de
responsaveis demorou **1.016 ms**. Nao foi uma consulta pesada: ela esperou o lock.

Referencias: [server.py:2514](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/server.py:2514>)
e [server.py:2560](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/server.py:2560>).

Correcao recomendada: ler o estado local e liberar conexao/lock antes de
qualquer I/O externo. Carregar arquivos por demanda ou atualizar separadamente,
com prazo total e cache, inclusive para ausencia de documentos. Testar duas
operacoes simultaneas com a fonte externa lenta.

### F5. Media: o Bloco 1 oculta a paginacao durante a verificacao online

Com 24 resultados locais e dez linhas exibidas, nao havia acesso a proxima
pagina enquanto o PNCP estava sendo verificado. Depois da conclusao, a interface
mostrou pagina 1 de 3. A consulta local ja estava pronta.

Referencia: [SearchBlock.tsx:582](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/frontend/src/components/SearchBlock.tsx:582>).

Correcao recomendada: manter navegavel a paginacao local enquanto o enriquecimento
online ocorre. Separar estado/contagem da busca local e da atualizacao remota;
preservar filtros e pagina e evitar respostas atrasadas sobrescrevendo a navegacao.

### F6. Media: links de catalogo antigo permanecem apos editar os itens

**Bloco 7.** Gerar arquivos, editar a descricao e observar que `Arquivos prontos`
e o mesmo link JSON continuam disponiveis. O arquivo baixado manteve a descricao
anterior, embora a tabela exibisse a revisao.

Referencia: [CatalogGeneratorBlock.tsx:80](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/frontend/src/components/CatalogGeneratorBlock.tsx:80>).

Correcao recomendada: invalidar exports a cada edicao; vincular cada exportacao
a uma revisao imutavel dos itens e descartar respostas de exportacoes obsoletas.
Sinalizar claramente quando os arquivos precisam ser regenerados.

### F7. Media: o PDF de catalogo corta texto silenciosamente

**Bloco 7.** Uma descricao de 1.323 caracteres com sentinela final foi exportada;
a sentinela nao aparece no texto do PDF. O codigo limita cada campo a 800
caracteres por meio de `[:800]`, sem indicar o corte ao usuario.

Referencia: [catalog_generator.py:178](<C:/Users/ducor/OneDrive/Documentos/Pregão/ocr_edital_web/catalog_generator.py:178>).

Correcao recomendada: paginar descricoes completas, permitindo fragmentacao
de linhas extensas, e testar o conteudo da primeira e da ultima pagina. Nao
substituir especificacoes completas por cortes silenciosos.

## Cobertura dos itens

Contagens observadas na base real, independentes da massa ficticia dos testes:

| Indicador | Valor |
| --- | ---: |
| Oportunidades armazenadas | 301.700 |
| Itens armazenados | 853.876 |
| Oportunidades com pelo menos um item | 68.093 (22,6%) |
| Oportunidades sem itens | 233.607 (77,4%) |
| Oportunidades com encerramento futuro informado | 27.612 |
| Dessas, com itens | 8.476 (30,7%) |
| Dessas, sem itens | 19.136 (69,3%) |

Ter um item nao prova que todos os itens daquela oportunidade foram coletados.
Esses percentuais sao um limite superior da cobertura completa por oportunidade.
Os numeros de prazo futuro nao incluem registros sem encerramento informado.

O filtro encontrou os 12 resultados esperados na massa controlada buscando
`cadeira` somente no texto dos itens. Isso valida esse cenario do filtro, mas
nao supre a ausencia dos itens na base real. A indexacao pendente deve ser
tratada como prioridade de qualidade dos dados, com fila retomavel, limites
de requisicao, deduplicacao, tentativas controladas e medicao de completude.

## Tempos observados

API local real; tres requisicoes sequenciais por operacao. Cache existente nao
foi apagado. Medidas incluem HTTP e leitura do corpo, nao o tempo completo de
interacao/renderizacao do navegador. Nao sao percentis de carga nem SLA.

Periodo da busca: encerramento de 31/08/2026 a 29/09/2026, incluindo publicadas
sem encerramento conforme a opcao atual do app.

| Operacao | Mediana | Maior amostra | Resultado |
| --- | ---: | ---: | --- |
| Busca ampla, pagina 1 | 844 ms | 931 ms | 28.982 correspondencias; 10 por pagina |
| Busca por cadeira | 344 ms | 375 ms | 459 correspondencias |
| Busca por UF SP | 206 ms | 208 ms | 5.693 correspondencias |
| Busca ampla, pagina 2 | 719 ms | 727 ms | Total preservado |
| Detalhe de oportunidade com itens | 56 ms | 325 ms | HTTP 200 |
| Identificacao de 90 itens locais | 10 ms | 18 ms | HTTP 200 |
| Lista de negocios | 32 ms | 37 ms | 1 negocio real |
| Detalhe de negocio | 40 ms | 147 ms | HTTP 200 |
| Templates | 24 ms | 25 ms | 2 modelos |
| Responsaveis | 22 ms | 28 ms | 2 registros |

Um catalogo real com um item terminou em aproximadamente **1,06 s**, observado
com consulta de status a cada 1 s; a aceitacao do job levou 41 ms. O tempo real
de conclusao pode ter sido menor que a observacao. Nao representa extracao fria,
OCR, catalogos grandes ou situacao de indisponibilidade do PNCP.

Na base isolada, sem rede externa: processar uma proposta com um item levou
33 ms; analisar template, 10 ms; gerar Word, 97 ms; exportar quatro formatos
de catalogo, 39 ms. Esses tempos nao devem ser usados como desempenho em producao.

## Fluxos e boas praticas observadas

| Bloco | Fluxo examinado | Resultado |
| --- | --- | --- |
| 1 | Filtros locais, palavra em itens, contagem, pagina seguinte e anterior | Aprovado na massa controlada; F5 e cobertura pendentes |
| 1 | Detalhamento, selecao antes de salvar e reabertura | Aprovado |
| 1 para 2/4/7 | Transferencia de somente um item selecionado | Aprovado |
| 2 | Processamento local, template, composicao, arraste da tabela e largura de colunas | Aprovado no fluxo nominal |
| 2 | Geracao de Word e preservacao entre exportacoes | Geracao funciona; F1/F2 impedem aprovacao geral |
| 4 | Kanban/lista/tabela, anotacoes, item selecionado e checklist | Aprovado |
| 4 | Avanco a qualificacao e historico | Aprovado; I/O sob lock e gargalo reproduzido |
| 7 | Processar selecao sem documentos, revisar e exportar XLSX/CSV/JSON/PDF | Funciona; F3/F6/F7 pendentes |

Pontos positivos: contratos de dados tipados no frontend, testes de regressao
existentes, calculos monetarios com precisao apropriada, consulta local de itens,
deduplicacao de importacao de negocio, validacao de entradas em varias rotas,
estrutura DOCX separada e replica HTML para reorganizacao visual.

Riscos adicionais encontrados por leitura, sem teste de carga prolongada:

- Bloco 7 faz polling a cada 900 ms por `setInterval`, sem impedir sobreposicao
  quando uma resposta demora mais que o intervalo. Preferir agendamento depois
  da conclusao da requisicao, cancelamento e backoff.
- Jobs de catalogo vivem em memoria, com uma thread por inicio e sem limite
  global/expiracao visivel. Faltam fila limitada e politica de retencao/retomada.
- A listagem de negocios carrega todos os registros. Foi medida com apenas
  um negocio real; isso nao valida o custo com milhares de negocios.
- O detalhe de oportunidade aguarda o enriquecimento externo antes de responder
  quando faltam itens/documentos. O lock de enriquecimento de documentos e global.
- Boa parte dos `fetch` nao tem prazo total/cancelamento. Um timeout de transporte
  precisa ser distinto de resultado vazio e preservar os dados locais.
- `server.py` concentra varias responsabilidades. Separar modulos gradualmente
  ajuda testes/manutencao; reescrever o backend nao e pre-requisito para corrigir
  as falhas concretas desta auditoria.

## Ordem recomendada de correcao

1. F1/F2: impedir misturar editais e sobrescrever documentos.
2. F3/F6/F7: revalidar revisoes e garantir fidelidade/completude dos exports.
3. F4/F5: retirar I/O remoto de locks e liberar navegacao local durante atualizacoes.
4. Completar indexacao de itens abertos/futuros e medir cobertura completa.
5. Acrescentar testes automatizados de interface para respostas fora de ordem,
   edicao durante geracao, indisponibilidade externa e paginacao concorrente.
6. Definir metas medidas de latencia por volume, com aquecimento identificado,
   medicao p50/p95/p99 e carga controlada antes de prometer desempenho geral.

## Evidencias e reproducao

- `checks.json`: 16 probes HTTP/integracao e os quatro criterios que falharam.
- `browser-checks.json`: cenarios de navegacao e tres falhas da interface.
- `live-timings.json`: amostras brutas das 11 operacoes HTTP reais.
- `catalog-live.json`: unico job real com um item.
- `coverage.json`: contagens de cobertura da base.
- Executor: `ocr_edital_web/scripts/audit_blocks.py`.

Com o Python do projeto, a partir de `ocr_edital_web`:

```powershell
python -m unittest -q
python scripts/audit_blocks.py checks --output reports/audit-checks.json
python scripts/audit_blocks.py measure --output reports/audit-timings.json
python scripts/audit_blocks.py coverage --output reports/audit-coverage.json
python scripts/audit_blocks.py serve --delay-process 4 --delay-online 1
```

`serve` imprime uma porta temporaria livre e usa apenas massa ficticia. Encerre
com Ctrl+C ao terminar. `checks` publica `passed: false` para defeitos detectados;
seu codigo de saida indica a execucao da auditoria, nao aprovacao do produto.

## Limites desta conclusao

Nao houve auditoria exaustiva de todos os editais/portais, comparacao integral
com o PNCP, teste de carga prolongada, certificacao de acessibilidade/mobile,
analise de seguranca completa ou validacao visual de todos os templates/exports.
Nao foram executadas exclusoes de negocios reais. Os testes de arraste foram
desktop. A existencia de 230 testes verdes nao demonstra ausencia de falhas;
os probes e a navegacao desta auditoria mostram lacunas da cobertura atual.
