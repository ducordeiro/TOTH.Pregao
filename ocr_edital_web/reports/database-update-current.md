# Atualizacao do banco Toth

Gerado em 13/09/2026 21:39:31 -0300.

## Funcionamento

1. Oportunidades: fila de 2026-06-01 a 2026-09-13, por dia/modalidade, das datas mais recentes para as antigas. Consulta Compras.gov quando ha equivalencia e usa PNCP como alternativa. Paginas e identidades sao verificadas; unidades incompletas ficam pendentes para retomada.
2. Itens: o extrator existente consulta as oportunidades sem itens. As oportunidades inseridas pela primeira fila passam a ser elegiveis. Tres trabalhadores, com controle de tentativas e espera entre requisicoes.
3. Indexacao: os metodos do repositorio atualizam o indice textual ao gravar oportunidades e lotes de itens. O indice fica disponivel ao Bloco 1 apos o commit da transacao.

## Progresso observado

| Etapa | Situacao |
| --- | --- |
| Processo de oportunidades ativo | True (PID 3300) |
| Unidades concluidas | 34 de 1995 |
| Unidades com falha nesta passagem | 0 |
| Novas oportunidades / atualizadas nesta execucao | 109 / 65 |
| Processo de itens ativo | True (PID 13256) |
| Tentativas de itens | 19989 de 124067 (16.11%) |
| Oportunidades preenchidas / tentativas falhas | 18791 / 1198 |
| Itens gravados nesta execucao | 324521 |
| Pendencias estimadas na fila atual de itens | 104078 |
| Total de oportunidades no banco | 356020 |
| Total de itens no banco | 3033438 |
| Entradas de oportunidade no indice | 356020 |
| Oportunidades sem entrada no indice | 0 |

## Previsoes

- Primeira passagem pela fila atual de itens: cerca de 34.3 horas, ou 15/09/2026 07:57, se o computador continuar ligado, conectado e no ritmo atual.
- Primeira passagem pela fila de oportunidades: 1.8 horas (preliminar). Dias vazios e dias com muitas paginas possuem custos diferentes; a estimativa inicial pode variar bastante.
- Indexacao: ocorre durante a gravacao; nao existe um lote separado aguardando o fim de toda a coleta.

As previsoes sao para tentativas das filas observadas. Novas oportunidades aumentam o trabalho de itens. Falhas nao equivalem a registros concluidos com sucesso, e oportunidades com itens parcialmente existentes exigem reconciliacao especifica. Portanto nao ha prazo comprovado para cobertura integral de todos os dados externos.

O coletor de oportunidades realiza uma passagem retomavel pelo periodo configurado. Ao terminar parcial, as unidades nao concluidas permanecem no arquivo de progresso; uma nova execucao do mesmo comando retoma essas unidades. Dias posteriores a data final exigem atualizar o parametro date-to. Nao foi criado agendamento automatico nem servico de reinicio do Windows.

Para atualizar este relatorio, executar a partir de ocr_edital_web: `python scripts/database_update_report.py`.
