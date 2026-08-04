# Relatório de tempo de resposta — detalhamento do Bloco 1

Data do teste: 04/08/2026  
Ambiente: aplicação local em `http://127.0.0.1:8765`, com consultas reais ao PNCP.

## Objetivo

Medir o tempo percebido pelo usuário ao abrir o detalhamento de uma oportunidade no Bloco 1 e separar o custo da interface, do processamento local e das consultas externas.

## Metodologia

Foram executadas três verificações:

1. Abertura real do modal pela interface do Bloco 1.
2. Chamadas HTTP reais para `/api/oportunidades/detalhe`, usando oportunidades retornadas pela pesquisa do PNCP.
3. Execução isolada do processamento local com as dependências externas simuladas, em 200 repetições.

As chamadas HTTP receberam um limite de 30 segundos. Uma chamada que não terminou nesse intervalo foi registrada como timeout.

## Resultados

### Retorno visual da interface

| Medição | Resultado |
|---|---:|
| Clique até o modal exibir o estado de carregamento | 322 ms |

O modal responde rapidamente ao clique e informa que os dados oficiais estão sendo carregados. A renderização inicial não é o gargalo.

### Detalhamento real pelo backend

| Oportunidade | Execução | Resultado | Tempo |
|---|---:|---|---:|
| Edital nº 015/2026 — Borba/AM | 1 | Timeout | > 30,00 s |
| Edital nº 015/2026 — Borba/AM | 2 | Timeout | > 30,00 s |
| Edital nº 015/2026 — Borba/AM | 3 | Sucesso, HTTP 200 | 18,52 s |
| Edital nº 015/2026 — Borba/AM | 4 | Timeout | > 30,00 s |
| Edital nº 015/2026 — Borba/AM | 5 | Timeout | > 30,00 s |
| Edital nº PCE 173/2026 — Palhoça/SC | 1 | Timeout | > 30,00 s |

Resumo da amostra:

- 6 chamadas observadas.
- 1 chamada concluída: 18,52 segundos.
- 5 timeouts: taxa de 83,3% no limite de 30 segundos.
- Tempo mediano observado: superior a 30 segundos.
- Mesmo edital apresentou grande variação entre tentativas.

### Processamento local isolado

| Indicador | Tempo |
|---|---:|
| Média | 1,434 ms |
| Mediana | 1,197 ms |
| P95 | 2,490 ms |
| Máximo | 16,934 ms |

O processamento local é praticamente instantâneo quando as respostas externas já estão disponíveis.

## Diagnóstico

O tempo total está concentrado na obtenção de dados externos. A rota de detalhamento executa, em paralelo:

- consulta dos metadados da contratação;
- consulta dos itens;
- consulta da lista de arquivos.

Depois dessas três consultas, o fluxo ainda tenta localizar, baixar e interpretar o edital ou Termo de Referência para comparar seus itens com a API. Essa segunda fase ocorre antes da resposta HTTP ser devolvida ao modal.

Cada consulta ao PNCP pode realizar duas tentativas de até 18 segundos. Respostas malsucedidas não são armazenadas no cache, por isso novas aberturas podem repetir toda a espera. O cache de sucesso também é temporário, com validade de cinco minutos para respostas da API e quinze minutos para documentos processados.

## Conclusão

O detalhamento do Bloco 1 não atende atualmente a uma meta interativa de resposta. A interface oferece retorno visual adequado em menos de meio segundo, mas o conteúdo permanece bloqueado pela integração externa, normalmente por mais de 30 segundos.

Classificação do resultado: **crítico**.

## Recomendações

1. Retornar primeiro metadados, itens e arquivos da API; executar a leitura/comparação do edital em segundo plano.
2. Exibir os dados da API assim que estiverem disponíveis, com um status separado de “Conferindo documento oficial”.
3. Adicionar cache para falhas e timeouts por um período curto, evitando repetição imediata de chamadas que acabaram de falhar.
4. Criar um cache único do detalhamento completo por contratação.
5. Definir limite de tempo menor para a resposta inicial, com degradação controlada para dados somente da API.
6. Registrar métricas separadas para metadados, itens, arquivos, download e extração do documento.

Meta sugerida após a alteração:

- retorno inicial com dados da API: até 2 segundos no P95;
- conferência do documento: assíncrona, sem bloquear o modal;
- nova abertura com cache: até 500 ms no P95.
