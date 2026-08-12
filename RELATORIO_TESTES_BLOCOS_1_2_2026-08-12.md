# Relatorio de testes - Blocos 1 e 2

Data: 12/08/2026

Aplicacao testada: TOTH Pregao em `http://127.0.0.1:8768`

## Resumo executivo

Os fluxos principais dos Blocos 1 e 2 funcionaram de ponta a ponta. A busca retornou dados da base interna, a oportunidade foi enviada ao Bloco 2, o item foi extraido, a proposta foi processada, a previa em PDF foi criada e o Word foi gerado e validado.

O principal problema e desempenho. As consultas amplas do Bloco 1 ficaram entre 4,2 s e 16,7 s no servidor ativo. No Bloco 2, carregar um edital levou cerca de 21,6 s, processar a proposta 16,0 s e gerar a previa 22,3 s. A geracao final do Word foi mais rapida, em 2,8 s.

Tambem foi identificado que o processo da porta 8768 esta executando uma versao anterior do backend. O codigo atual salvo reconhece os itens estruturados de um edital usado no teste, enquanto o processo antigo retorna erro 500 para esse mesmo edital.

## Testes automatizados

| Camada | Resultado | Duracao |
| --- | ---: | ---: |
| Frontend Vitest | 9 de 9 testes aprovados | 1,80 s |
| TypeScript | Sem erros de tipagem | 9,9 s |
| Backend e ETL | 108 de 108 testes aprovados | 14,69 s |

Total: 117 testes automatizados aprovados, sem falhas.

## Bloco 1 - Consulta PNCP

Funcionalidades verificadas:

- abertura do Bloco 1;
- consulta na base interna reorganizada;
- retorno de 10 registros por pagina;
- paginacao;
- filtro por palavra-chave;
- filtro combinado por UF e modalidade;
- consulta sem resultados;
- abertura dos dados detalhados;
- envio de uma oportunidade ao Bloco 2;
- ausencia de erros no console do navegador.

### Tempos do servidor ativo - porta 8768

Cada medicao de API foi repetida cinco vezes.

| Operacao | Mediana | Media | Faixa observada |
| --- | ---: | ---: | ---: |
| Carregar frontend | 9,6 ms | 38,4 ms | 4,5 a 132,6 ms |
| Listar templates | 11,4 ms | 15,2 ms | 8,0 a 33,5 ms |
| Listar responsaveis | 204,2 ms | 220,4 ms | 143,5 a 310,5 ms |
| Busca ampla, pagina 1 | 5,30 s | 7,28 s | 4,22 a 16,74 s |
| Busca ampla, pagina 2 | 7,03 s | 6,19 s | 4,51 a 7,34 s |
| Busca com palavra-chave | 4,81 s | 4,49 s | 3,46 a 5,59 s |
| Busca por SP + modalidade 6 | 1,36 s | 1,57 s | 1,11 a 2,08 s |
| Busca sem correspondencia | 3,33 s | 3,68 s | 2,92 a 5,16 s |
| Detalhe ja armazenado | 126,5 ms | 120,2 ms | 43,2 a 198,3 ms |

Durante o teste pela interface, a troca para a pagina 2 levou aproximadamente 15,6 s sob carga concorrente.

### Tempos do codigo atual - porta temporaria 8770

| Operacao | Mediana de 3 execucoes |
| --- | ---: |
| Busca ampla | 3,58 s |
| Busca com palavra-chave | 2,27 s |
| Busca por SP + modalidade 6 | 836,7 ms |
| Detalhe armazenado | 19,9 ms |

O codigo atual melhorou os tempos, mas a busca ampla ainda esta acima de uma meta confortavel de ate 1 segundo.

### Diagnostico do Bloco 1

O banco utiliza o indice de status, mas precisa criar uma arvore temporaria para ordenar os resultados. A consulta tambem executa um `COUNT(*)` completo antes de buscar a pagina. Com mais de 220 mil oportunidades e gravacoes simultaneas da extracao, isso eleva a latencia.

O total variou durante a navegacao, de 18.817 para 18.865 e depois continuou aumentando. Isso e coerente com novos registros entrando no banco durante o teste, mas pode causar deslocamento ou repeticao de registros entre paginas baseadas em offset.

## Bloco 2 - Gerar proposta

Fluxo real verificado na porta 8768:

- recebimento automatico do link selecionado no Bloco 1;
- consulta e identificacao de item do edital;
- selecao do item;
- preenchimento de marca e valor unitario;
- calculo do valor total;
- processamento da proposta;
- geracao da previa em PDF;
- geracao do arquivo Word;
- abertura estrutural do DOCX gerado.

| Operacao pela interface | Tempo observado | Resultado |
| --- | ---: | --- |
| Carregar e identificar o edital | 21,6 s | Aprovado, 1 item |
| Processar proposta | 16,0 s | Aprovado |
| Gerar previa em PDF | 22,3 s | Aprovado |
| Gerar Word | 2,8 s | Aprovado |

O Word gerado tinha 69.787 bytes, 17 paragrafos, uma tabela e duas linhas. O arquivo abriu corretamente pela biblioteca de validacao DOCX.

No codigo atual, um edital com 33 itens ja estruturados foi identificado em 1,06 s na primeira consulta e 13 ms na repeticao em cache. Isso confirma que priorizar os itens armazenados no backend reduz bastante o tempo.

## Problemas encontrados

### Alta prioridade

1. Servidor desatualizado na porta 8768.

O backend em execucao foi iniciado em 07/08/2026 e nao carregou as alteracoes atuais. Um edital com 33 itens presentes no banco retorna erro 500 no processo antigo, enquanto o codigo atual responde 200 e entrega os 33 itens.

2. Busca ampla lenta no Bloco 1.

A mediana foi de 5,30 s no servidor ativo. O plano SQLite mostra ordenacao em arvore temporaria e o `COUNT(*)` percorre uma quantidade relevante de registros. O efeito piora durante a extracao concorrente.

3. Bloco 2 ainda depende do PNCP e dos documentos para etapas de processamento.

A identificacao atual pode usar a base estruturada, mas o endpoint `/process` volta a buscar arquivos e dados externos. Essa duplicacao explica parte dos 16 s e pode falhar quando o PNCP estiver indisponivel.

### Media prioridade

4. Previa em PDF depende de uma sessao interativa do Microsoft Word.

Na porta principal a previa funcionou. Em um processo temporario sem sessao COM interativa, a conversao falhou com erro de sessao de logon. Isso torna a funcionalidade sensivel a como o servidor e iniciado.

5. Unidade inconsistente em alguns itens estruturados.

No edital de 33 itens, a unidade retornada pela base apareceu como `100`, igual a quantidade, em vez de uma unidade de medida. O processamento final normaliza para `UND`, mas a exibicao inicial pode confundir o usuario.

6. Paginacao instavel durante atualizacao da base.

Como o total e a ordenacao podem mudar entre requisicoes, a pagina 2 pode nao representar exatamente a continuacao da pagina 1 durante uma extracao intensa.

## Recomendacoes de otimizacao

Ordem sugerida:

1. Reiniciar o servidor da porta 8768 para carregar o backend atual.
2. Fazer o `/process` reutilizar os itens e metadados ja entregues pela identificacao, evitando baixar e extrair o mesmo edital novamente.
3. Criar indice composto voltado a `radar_status`, `proposal_end_at` e `published_at`, validando o ganho com `EXPLAIN QUERY PLAN`.
4. Evitar recalcular o total exato em toda pagina ou aplicar cache curto ao `COUNT(*)` por conjunto de filtros.
5. Adotar paginacao por cursor para manter estabilidade enquanto o ETL grava novos registros.
6. Substituir ou proteger a conversao COM do Word com uma alternativa executavel como servico e mensagens de erro mais claras.
7. Corrigir a normalizacao do campo de unidade durante a extracao dos itens.
8. Adicionar testes de interface automatizados para os fluxos completos dos Blocos 1 e 2.

## Conclusao

Status funcional: aprovado com ressalvas.

O sistema executa o fluxo principal de consulta e geracao de proposta. A prioridade imediata e alinhar o processo em execucao com o codigo atual e eliminar a segunda extracao do edital no `/process`. Depois disso, a otimizacao da consulta SQLite deve reduzir o tempo do Bloco 1 e tornar a experiencia mais consistente durante a atualizacao da base.
