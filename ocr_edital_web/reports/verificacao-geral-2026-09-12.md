# Verificacao operacional do Toth

Data: 12/09/2026, aproximadamente 17h40-17h51, America/Sao_Paulo.

## Conclusao

O app responde e a extracao de itens continua ativa. Foi identificado um bloqueio de rede no servidor anterior, resolvido nesta verificacao operacional com reinicializacao autorizada do servidor. A consulta real posterior obteve dados de Compras.gov e PNCP. Isso nao significa cobertura completa: existem limites internos de tempo/paginacao, itens ainda pendentes e latencia variavel na busca por palavra-chave.

Nao foram alteradas regras de negocio dos blocos, filtros, esquema do banco ou dados manualmente. A atualizacao de oportunidades usou a rota de reconciliacao existente. Foram adicionados somente roteiro de auditoria e relatorios. As alteracoes anteriores do Bloco 7 passaram a ser carregadas pelo novo servidor.

## Servidor e continuidade

- Processo anterior: PID 19816. Registros de consultas apresentavam WinError 10013 (acesso a socket proibido), nao ausencia de oportunidades no provedor.
- Novo servidor: PID 9304, iniciado sem janela, porta 8765. Pagina inicial e rotas locais retornaram HTTP 200.
- Extrator preservado: PID 25000, run 5490b548d56a4825b97fe784036015ed. Nenhum extrator duplicado foi iniciado.
- Prioridade configurada: Compras.gov, depois PNCP. Ordem da fila: publicacao decrescente. O modo all nao limita a fila pela data_to exibida no arquivo de status.
- Na leitura de 17h48: 51.204 tentativas, 50.307 oportunidades preenchidas, 597.556 itens registrados e 897 falhas nesta execucao. Esses numeros sao do lote, nao o total do banco nem prova de completude dos itens preexistentes.
- Falhas do lote nessa leitura: 773 HTTP 404, 75 HTTP 502, quatro timeouts, tres respostas sem descricao e 42 outras falhas. Nao foi feito descarte de oportunidades nem relaxamento de validacao para contorna-las.

## Consulta recente executada

Consulta do app para publicacao em 11-12/09/2026, sem palavra-chave ou UF, com reconciliacao:

- Compras.gov: 159 registros processados, quatro inseridos e 155 atualizados. Acionou fallback por atingir a janela interna de consulta de 12 segundos.
- PNCP: reconciliacao finalizada com sucesso. Resumo combinado: 3.000 registros processados, 969 inseridos, 321 atualizados e 1.710 sem alteracao.
- Resultado marcado como incompleto: truncated=true, complete=false. Foram verificadas 12 paginas; nao houve 429, timeout ou pagina falha nessa resposta do PNCP. A limitacao de paginas do app impediu afirmar cobertura integral.
- source_total=38.775 se refere ao universo da consulta remota antes de todos os filtros locais, nao a 38.775 oportunidades necessariamente publicadas nos dois dias selecionados.

## Banco e indexacao

Banco: ocr_edital_web/data/pncp.sqlite3, aproximadamente 9,98 GB, journal_mode=WAL.

Na primeira leitura havia 354.707 oportunidades, 2.522.776 itens e 354.707 entradas no indice textual. Na leitura posterior a reconciliacao havia 355.676 oportunidades e 2.532.110 itens. A coleta permaneceu ativa, portanto as contagens sao fotografias de momentos distintos, nao uma transacao global congelada.

- PRAGMA quick_check da tabela opportunities: ok, 22,84 segundos.
- PRAGMA quick_check integral: interrompido pelo limite preventivo de 120 segundos. Verificacao especifica de opportunity_items tambem atingiu o limite de 60 segundos. Essas interrupcoes nao comprovam corrupcao nem permitem declarar integridade integral do arquivo.
- Existem indices de identidade, datas, regiao, modalidade e relacionamento dos itens com a oportunidade.
- Amostra das 50 oportunidades mais recentes com itens: 822 itens, sem identificadores de item duplicados, sem descricao vazia e com descricoes presentes no conteudo do indice.
- Consulta FTS MATCH: 50 de 50 oportunidades dessa amostra encontradas. Nao representa validacao integral dos 2,5 milhoes de itens nem confronto de cada item com o provedor.
- Na primeira leitura de setembro: 19.670 oportunidades, 87 sem itens; 54 classificadas como material estavam sem itens.
- Apos descoberta de novas oportunidades: 20.639 oportunidades em setembro, 1.037 sem itens; 732 classificadas como material sem itens. O aumento decorre principalmente da entrada de novas oportunidades na fila, nao de exclusao de itens. A classificacao de material e a classificacao armazenada pelo app.

## Tempos e testes

Requisicoes HTTP locais sequenciais, tres por rota e 50 detalhamentos distintos, com extracao ativa. Tempos incluem rede local e backend, nao renderizacao do navegador.

| Funcionalidade | Mediana | Maior tempo |
| --- | ---: | ---: |
| Pagina inicial | 12 ms | 49 ms |
| Templates | 15 ms | 32 ms |
| Responsaveis | 23 ms | 63 ms |
| Negocios | 19 ms | 45 ms |
| Kanban | 22 ms | 62 ms |
| Busca ampla | 46 ms | 164 ms |
| Palavra-chave cadeira | 302 ms | 7.297 ms |
| Filtro UF | 80 ms | 1.072 ms |
| Detalhamento local, 50 registros | 15 ms | 87 ms |

Todos os 74 pedidos locais desse roteiro retornaram HTTP 200. Apos reiniciar, a busca por cadeira variou entre 455 e 3.815 ms em tres chamadas; a busca ampla entre 32 e 510 ms. Nao foi observado desempenho uniformemente instantaneo.

259 testes de backend aprovados (53,885 s), incluindo servidor, catalogos, ETL, prioridade e fallback. 41 testes de frontend aprovados (2,79 s). As suites usam dados controlados; nao representam teste visual manual de todos os fluxos nem conversao real de todos os documentos nesta rodada.

## Pendencias e recomendacoes cautelosas

1. Busca por palavra-chave: os nove pedidos medidos apos reiniciar tiveram cache miss. A chave inclui tamanho/mtime do banco e WAL (server.py, internal_opportunity_database_revision). A extracao e reconciliacao alteram continuamente esses arquivos, invalidando o cache. Isso explica perda de reaproveitamento, mas nao isola sozinho todo o custo SQL/I/O. Antes de alterar a politica, medir o plano SQL e separar invalidacao por dados relevantes; evitar simplesmente servir resultados antigos por tempo indefinido.
2. Descoberta completa: desacoplar coleta paginada retomavel da janela de busca interativa, mantendo checkpoint por fonte/periodo/modalidade. Aumentar limites indiscriminadamente na busca pode piorar a espera e a carga remota.
3. Integridade completa: repetir verificacao integral em janela de menor uso ou numa copia consistente feita pela API de backup do SQLite. Nao copiar somente o arquivo principal enquanto WAL estiver ativo e nao executar VACUUM/REINDEX por tentativa.
4. Completude de itens: o extrator de ausentes nao garante reparacao de oportunidades que ja tenham apenas parte dos itens. E necessario reconciliar contagem e identidade com evidencia do provedor, sem substituir itens validos cegamente.
5. Falhas: distinguir 404 persistente de 502/timeout transitorio, respeitando tentativas limitadas e pausas. Nao tratar todos os erros como oportunidade inexistente.

## Evidencias

- scripts/verify_live_database.py: roteiro limitado de leitura SQLite e HTTP local.
- reports/live-database-2026-09-12.json: contagens, indices, amostra e tempos anteriores ao reinicio.
- reports/live-after-restart-2026-09-12.json: tempos e cabecalhos de cache posteriores ao reinicio.
- reports/live-online-2026-09-12.json: resultado da consulta real reconciliada.
- data/server-20260912-verified.stdout.log e .stderr.log: servidor atual.

Nenhum commit ou push realizado nesta verificacao.
