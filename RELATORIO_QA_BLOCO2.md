# Relatorio de QA sistemico - Bloco 2

Data do teste: 05/08/2026
Ambiente: aplicacao local em `http://127.0.0.1:8765`
Escopo: Bloco 2 - Gerar proposta

## Objetivo

Validar o fluxo sistemico do Bloco 2, verificando se o processo assumido pelo
sistema e coerente, funcional e otimizado para o usuario gerar uma proposta a
partir de um link PNCP.

## Agentes de referencia

- `fritz-qa-flow-guard`: validacao da jornada ponta a ponta.
- `fritz-qa-smoke`: validacao complementar de contratos e evidencias.

## Fluxo testado

1. Abrir a aplicacao local.
2. Navegar do Bloco 1 para o Bloco 2.
3. Informar link PNCP.
4. Carregar itens do edital.
5. Selecionar itens.
6. Informar valores unitarios.
7. Processar a proposta.
8. Gerar pre-visualizacao em PDF.
9. Validar contrato de geracao Word por API.

Link PNCP usado:

`https://pncp.gov.br/app/editais/45780087000103/2026/43`

## Comandos executados

```powershell
npm run typecheck
npm test -- --run
npm run build
& 'C:\Users\ducor\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest -v
```

Tambem foram executadas chamadas HTTP locais para:

- `/api/templates`
- `/api/responsaveis`
- `/identify-items`
- `/process`
- `/proposal-preview`
- `/generate`

E validacao automatizada da interface via Chromium headless.

## Resultados automatizados

| Camada | Resultado |
|---|---:|
| Backend Python | 87 testes aprovados |
| Frontend typecheck | aprovado |
| Frontend Vitest | 2 arquivos / 9 testes aprovados |
| Frontend build | aprovado |

## Tempos observados

### Contratos de API

| Etapa | Resultado | Tempo |
|---|---|---:|
| Templates | 2 templates retornados | 176 ms |
| Responsaveis | 2 responsaveis retornados | 193 ms |
| Identificacao de itens, cache frio | 10 itens, sem divergencia | 5.899 ms |
| Processamento da proposta, cache frio | HTTP 200, 10 itens extraidos | 13.430 ms |
| Pre-visualizacao PDF | PDF gerado | 8.440 ms |
| Geracao Word | DOCX gerado | 652 ms |
| Download da pre-visualizacao | HTTP 200, `application/pdf`, 213.731 bytes | 204 ms |

### Jornada pela interface

| Etapa | Resultado | Tempo |
|---|---|---:|
| Carregamento inicial da home | H1 `Buscar oportunidades` | 898 ms |
| Navegacao para Bloco 2 | H1 `Gerar proposta` | 64 ms |
| Identificacao de itens com cache quente | 10 itens carregados | 862 ms |
| Processamento com 2 itens selecionados | 2 itens preparados | 181 ms |
| Pre-visualizacao pela UI | iframe PDF criado | 6.006 ms |

Nao houve erro de console durante a navegacao automatizada.

## Evidencias funcionais

- A aplicacao serviu corretamente o build React em `/`.
- O Bloco 2 abriu com os campos essenciais visiveis:
  - URL PNCP
  - marca
  - responsavel
  - template
  - itens do edital
  - acao de extrair tabelas e aplicar valores
- O link PNCP carregou 10 itens.
- A selecao de 2 itens resultou em exatamente 2 itens preparados.
- A pre-visualizacao retornou PDF valido por HTTP.
- O endpoint de geracao recusou corretamente payload sem `responsible_id`.
- A geracao Word com payload completo retornou arquivo DOCX valido.

Arquivo gerado na rodada:

`ocr_edital_web/outputs/Proposta_Final_PNCP_45780087000103_2026_43_1785954870.docx`

## Primeiro ponto de atrito

O maior custo do Bloco 2 esta na etapa de extracao/processamento inicial.
Mesmo quando o usuario seleciona poucos itens, o backend processa a base
completa do documento e devolve todos os itens; a selecao e aplicada no
frontend depois da resposta.

Impacto:

- selecionando 2 itens, o custo principal ainda foi o custo de extrair todos os 10;
- em editais maiores, o usuario pode sentir demora mesmo fazendo uma selecao pequena;
- o cache quente resolve a repeticao, mas a primeira execucao continua sendo a etapa critica.

## Classificacao das falhas

| Tipo | Situacao |
|---|---|
| Contrato | aprovado |
| Persistencia | aprovado com ressalva, pois a geracao registra documento e altera o SQLite local |
| UX | aprovado com ressalvas |
| Performance | aprovado com ressalvas |
| Fluxo ponta a ponta | aprovado |

## Recomendacoes de otimizacao

1. Aplicar `wanted_items` no backend antes de devolver o resultado final de `/process`,
   reduzindo payload, renderizacao e trabalho posterior.
2. Reutilizar explicitamente o resultado de `/identify-items` dentro de `/process`
   quando o link e o documento ja estiverem em cache.
3. Exibir no Bloco 2 um indicador separado para:
   - consulta PNCP;
   - extracao do documento;
   - montagem da proposta;
   - geracao da pre-visualizacao.
4. Tornar a pre-visualizacao opcionalmente assincrona em editais grandes, mantendo a
   tabela preparada disponivel imediatamente.
5. Criar metricas persistentes por etapa para comparar cache frio e cache quente.
6. Ajustar a area de itens para evitar que a acao principal pareca colada ao fim da
   tabela em resolucoes intermediarias.

## Recomendacao final

Classificacao final: **aprovado com ressalvas**.

O Bloco 2 esta funcional e pode seguir para uso controlado. A proxima melhoria
deve focar em reduzir o custo da primeira execucao de `/process`, principalmente
em editais maiores, e em tornar mais transparente para o usuario qual etapa esta
consumindo tempo.
