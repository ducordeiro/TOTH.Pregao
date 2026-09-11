# Auditoria da extracao e indexacao de itens

Data: 2026-09-10. Escopo exclusivo: `enrich_missing_pncp_items.py`, conectores
utilizados pelo extrator, persistencia e indice dos itens. Nenhum comportamento
de producao foi alterado e o processo em execucao nao foi interrompido.

## Conclusao

A extracao esta ativa e a amostra verificada foi persistida e indexada
corretamente. Isso nao significa cobertura integral nem ausencia de problemas:
ha uma falha reproduzida no controle de tentativas apos limite de requisicoes,
alem de limitacoes de completude, reprocessamento e observabilidade.

## Achados por prioridade

### P2 - Novas tentativas podem ignorar a pausa global de HTTP 429

Referencias: `scripts/enrich_missing_pncp_items.py:41` e `:60`;
`etl/connectors.py:50`.

O limitador atua uma vez por chamada de `get`, mas o cliente HTTP executa
suas tentativas internamente. A pausa de 60 segundos so e registrada quando
todas as tentativas terminam em erro. Uma resposta 429 seguida de sucesso
produziu duas tentativas HTTP, uma unica passagem pelo limitador e nenhuma
pausa registrada. Reproducao controlada, sem requisicoes externas.

Outra reproducao mostrou que uma thread que ja aguarda seu horario reservado
nao reavalia uma pausa global imposta por outra thread durante essa espera.

Impacto: requisicoes antecipadas durante limitacao do provedor, com risco de
mais falhas e demora. Nao foi observado 429 nos erros registrados deste lote
ate a leitura; trata-se de defeito reproduzido, nao da causa comprovada dos
erros atuais.

Recomendacao: aplicar o limitador em cada tentativa HTTP; registrar o bloqueio
assim que o 429 chegar e reavaliar o prazo compartilhado ao acordar. Preservar
limitadores independentes por provedor e testar concorrencia e Retry-After.

### P2 - Ter algum item salvo nao comprova que todos estao completos/indexados

Referencias: `scripts/enrich_missing_pncp_items.py:675` e `:710`;
`etl/repository.py:1428` e `:1435`.

A selecao exclui oportunidades que possuem qualquer linha em opportunity_items.
O teste local tambem considera qualquer linha suficiente. Portanto, uma
oportunidade anteriormente importada com apenas parte dos itens, com dados
invalidos ou com indice ausente nao sera reparada por este extrator.

Esta e uma limitacao do preenchimento de oportunidades sem itens, nao uma
prova de que os novos lotes estejam incompletos. O fluxo novo valida contagem,
duplicacoes e descricoes antes da gravacao.

Recomendacao: separar estados de itens ausentes, completos, parciais e falhos;
usar evidencia de completude do provedor e auditar o indice separadamente.
Nao apagar ou substituir itens existentes sem reconciliacao validada.

### P2 - Falhas recentes nao voltam a fila nesta mesma execucao

Referencias: `scripts/enrich_missing_pncp_items.py:306` e `:549`.

O extrator exclui todas as falhas do proprio run_id, mesmo depois do intervalo
de 12 horas. A regra evita repeticao infinita, mas uma oportunidade recente
com timeout pode continuar pendente enquanto oportunidades antigas avancam.
O parametro de 12 horas nao e um agendador de novas tentativas.

Recomendacao: fila de retentativas com proxima tentativa e limite por identidade,
distinguindo falhas transitorias de 404. Preservar a protecao contra ciclos
infinitos. A ordem por publicacao permanece correta entre registros elegiveis.

### P2 - Motivos de uso da fonte alternativa nao ficam no resumo da execucao

Referencia: `etl/preferred_source.py:171`.

Na consulta de auditoria, os 13.282 registros de sucesso do run atual tinham
URL do PNCP; nenhum tinha URL do Compras.gov. O motivo da troca e emitido via
logger INFO, mas nao aparece nos arquivos stdout/stderr observados nem nos
contadores por provedor. Assim, a prioridade configurada nao comprova uso
efetivo do Compras.gov.

Consulta real controlada para 07954480000179-1-023173/2026: Compras.gov
respondeu em 0,246 s com resultado vazio. Conferencia dos metadados confirmou
totalRegistros=0, totalPaginas=0 e paginasRestantes=0. PNCP forneceu os itens
dessa oportunidade no lote. Isso explica essa identidade, nao todas as demais.

Recomendacao: registrar contadores e motivos estruturados por provedor:
sucesso, vazio, timeout, limite, resposta invalida e paginacao incompleta.

## Verificacoes realizadas

- 84 testes existentes aprovados em 17,246 s: scripts.test_enrich_priority,
  test_etl e test_preferred_source. Incluem ordem recente, fallback, validacao
  de identidade, rejeicao de duplicados/parcialidade e integracao SQLite/FTS.
- Duas reproducoes controladas adicionais do problema de limitacao descrito.
- Processo Python 17020 confirmado ativo; contador do run continuou avancando.
- Banco consultado em modo somente leitura, com limite de tempo por consulta.
- Amostra distribuida de 100 oportunidades do run, totalizando 2.011 itens:
  contagens iguais aos recibos, sem chaves de item duplicadas, sem descricao
  vazia e com todas as descricoes presentes no conteudo FTS.
- Uma consulta MATCH por oportunidade da amostra: 100 de 100 encontradas.
- Leitura/verificacao local por oportunidade: mediana 3,16 ms e maximo
  587,40 ms. Estes tempos sao da auditoria SQLite, nao da interface/API.
- 118 falhas registradas na leitura: 101 HTTP 404 e 17 timeout/SSL.
  Nao apareceram erros de gravacao SQLite entre esses registros.
- Persistencia usa BEGIN IMMEDIATE, commit/rollback e verificacao de itens
  existentes dentro da transacao; nao grava o lote novo antes da validacao.

## Limites desta revisao

Nao foi realizada varredura integral de integridade do arquivo SQLite nem
reconsulta externa de cada item: a base esta em uso e esse trabalho adicionaria
carga relevante. A amostra nao garante completude historica de toda a base.
Os 84 testes nao cobriam o defeito de limitacao reproduzido separadamente.
O extrator enriquece oportunidades existentes: nao descobre sozinho novas
oportunidades publicadas fora do banco. O total inicial e finito, e o status
mostra tentativas processadas, nao percentual de cobertura validada da base.

## Proxima ordem de trabalho recomendada

1. Corrigir e testar o limitador por tentativa, isoladamente no extrator.
2. Registrar origem e motivo de fallback por tentativa.
3. Implementar retentativas limitadas para falhas transitorias recentes.
4. Auditar oportunidades com itens preexistentes e planejar reconciliacao
   de lacunas com backup, simulacao e validacao antes de qualquer substituicao.
