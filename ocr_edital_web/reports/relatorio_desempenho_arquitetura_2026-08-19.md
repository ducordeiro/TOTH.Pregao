# Relatorio de desempenho e arquitetura - Toth Pregao

Data da avaliacao: 19/08/2026

## Escopo e metodologia

- Servidor local: `http://127.0.0.1:8765`
- Medicoes HTTP sequenciais em loopback, sem latencia de Internet para rotas locais.
- Rotas pequenas: 20 repeticoes, com mediana (p50) e percentil 95 (p95).
- Rotas pesadas: 2 a 5 repeticoes para evitar carga excessiva no PNCP e geracao desnecessaria de arquivos.
- Banco avaliado com aproximadamente 276 mil oportunidades e 2,25 GB.
- Testes automatizados: 132 testes de backend e 9 testes de frontend aprovados.

Os numeros representam o ambiente atual desta maquina. Nao constituem teste de carga multiusuario.

## Resultados

| Funcionalidade | Resultado observado | Avaliacao |
|---|---:|---|
| Pagina inicial | p50 3,2 ms; p95 5,6 ms | Otimo |
| Templates | p50 4,3 ms; p95 6,0 ms | Otimo |
| Responsaveis | p50 43,2 ms; p95 58,5 ms | Bom |
| Kanban | p50 21,2 ms; p95 26,3 ms | Bom |
| Negocios | p50 45,0 ms; p95 61,0 ms | Bom |
| Itens do Bloco 2, persistidos | p50 4,1 ms; p95 5,7 ms | Otimo |
| Busca local de um dia, 1.676 resultados | mediana 1,34 s | Lento |
| Busca local de 19 dias, 25.336 resultados | mediana 1,94 s | Lento |
| Busca textual no periodo | mediana 1,67 s | Lento |
| Pagina 100 em periodo amplo, 134.529 resultados | mediana 5,02 s | Critico |
| Reconciliacao online PNCP | 1,22 a 1,69 s, mas parcial | Inconclusivo/instavel |
| Detalhe com documentos, primeira consulta | 579 ms | Aceitavel |
| Detalhe persistido, consulta seguinte | 25 ms | Otimo |
| Processamento da proposta, primeira chamada | 121 ms | Bom |
| Processamento da proposta, chamadas seguintes | 26 a 37 ms | Otimo |
| Geracao do Word | 281 a 354 ms | Bom |
| Pre-visualizacao PDF, sem cache | 10,24 s | Critico |
| Pre-visualizacao PDF, com cache | 83 ms | Otimo |
| Rascunho de catalogo, sem cache | 40,70 s | Critico |
| Rascunho de catalogo, com cache | 10 ms | Otimo |
| Exportacao completa do catalogo | 2,05 s | Aceitavel |

Durante a reconciliacao online, `publicacao` e `atualizacao` responderam, mas `proposta` retornou HTTP 429. O tempo curto dessa rodada nao significa sucesso: o resultado permaneceu parcial.

## Estrutura atual

Fluxo principal:

1. React chama as funcoes centralizadas em `frontend/src/api.ts`.
2. `ThreadingHTTPServer` recebe as requisicoes em `server.py`.
3. O servidor orquestra busca, extracao, proposta, catalogo e arquivos.
4. Os modulos `etl/` concentram conectores, mapeamento, classificacao e repositorio.
5. SQLite armazena oportunidades normalizadas, itens, documentos, auditoria e dados operacionais.
6. A pre-visualizacao cria um DOCX e usa Microsoft Word/PowerShell para converter em PDF.

Pontos positivos:

- Estrategia local-first no Bloco 1 e no Bloco 2.
- Persistencia dos itens obtidos sob demanda.
- Modelo normalizado separado dos registros brutos de auditoria.
- SQLite em modo WAL e indices para datas, regiao, modalidade e identidade PNCP.
- Reconciliacao de endpoints PNCP em paralelo.
- Cache para itens, documentos, catalogo e pre-visualizacao.
- Cobertura automatizada relevante para o tamanho atual do projeto.

## Gargalos e riscos

### 1. Busca local

A consulta executa `COUNT(*)`, junta classificacoes, ordena em arvore temporaria e depois aplica `LIMIT/OFFSET`. A busca textual usa `%termo%` e subconsulta correlacionada nos itens. O plano do SQLite confirmou `USE TEMP B-TREE FOR ORDER BY`.

O custo cresce com o periodo e com a pagina. A pagina 100 levou aproximadamente 5 segundos mesmo sem Internet.

### 2. Atualizacao PNCP acoplada a cada busca

O frontend apresenta o resultado local, executa a reconciliacao PNCP e depois repete a busca local. Navegacoes e novas consultas podem repetir a reconciliacao. Quando um endpoint falha, o resultado parcial nao entra no cache de sucesso, favorecendo novas chamadas e HTTP 429.

### 3. Crescimento da auditoria

O banco possui aproximadamente 2,25 GB. A tabela `source_records` ocupa 1.468 MiB, cerca de 69% do arquivo. Seus indices adicionam mais de 240 MiB. Sem politica de retencao, esse custo continuara crescendo e afetara backup, inicializacao e manutencao.

### 4. Processamentos frios

O rascunho do catalogo levou 40,7 segundos sem cache. Depois caiu para 10 ms. Isso mostra que download, leitura de documentos e extracao dominam o tempo e que o cache atual e decisivo.

A pre-visualizacao levou 10,2 segundos sem cache porque depende de automacao do Microsoft Word. A conversao e serializada por um lock global, limitando a vazao quando houver varios usuarios.

### 5. Colisao de nomes na geracao

O nome do Word usa `int(time.time())`. Duas geracoes no mesmo segundo produziram o mesmo nome, causando sobrescrita potencial e registros duplicados apontando para o mesmo arquivo.

### 6. Concentracao de responsabilidades

`server.py` possui aproximadamente 10 mil linhas e concentra HTTP, regras de negocio, cache, extracao e geracao. No frontend, `BusinessBlock.tsx` possui cerca de 1.474 linhas. Essa concentracao aumenta o custo de manutencao e o risco de regressao.

Caches e locks sao mantidos em memoria. Eles sao perdidos ao reiniciar e nao seriam compartilhados entre varios processos do servidor.

## Recomendacoes priorizadas

### Prioridade imediata

1. Trocar o nome de arquivo baseado em segundos por UUID ou timestamp em nanossegundos.
2. Desacoplar a sincronizacao PNCP do clique em Buscar. A tela deve consultar somente a base local e disparar uma atualizacao unica em segundo plano, protegida por TTL e chave de consulta.
3. Aplicar cooldown especifico para HTTP 429 e nao repetir o endpoint bloqueado durante navegacao/paginacao.

### Alto impacto

4. Implantar FTS5 para titulo, objeto, orgao e descricoes de itens.
5. Substituir paginacao por `OFFSET` por cursor/keyset nas paginas profundas.
6. Evitar `COUNT(*)` completo a cada pagina; usar contagem em cache ou calculada separadamente.
7. Rever a ordenacao por score para evitar a arvore temporaria em grandes conjuntos.
8. Definir retencao de `source_records`: manter o ultimo payload por fonte/identidade, compactar JSON e arquivar historico antigo.

### Processamento de documentos

9. Persistir o cache de documentos e extracoes por hash do arquivo, sobrevivendo ao reinicio.
10. Mover OCR, catalogo e conversao PDF para uma fila de workers, com progresso consultavel pela interface.
11. Manter um conversor aquecido ou avaliar LibreOffice headless em worker dedicado, sem bloquear a requisicao HTTP.
12. Persistir o cache da pre-visualizacao pelo fingerprint ja calculado.

### Evolucao arquitetural

13. Dividir `server.py` em rotas, servicos de aplicacao, repositorios, integracoes e workers.
14. Dividir os componentes React maiores por fluxo e responsabilidade.
15. Adicionar telemetria por endpoint: tempo de banco, rede, download, extracao, geracao e cache hit/miss.
16. Executar teste de carga concorrente depois das otimizacoes, com cenarios de 5, 10 e 25 usuarios.

## Ordem sugerida de execucao

1. Corrigir colisao de arquivo e repeticao das chamadas PNCP.
2. Otimizar a busca SQLite com FTS5, contagem em cache e keyset pagination.
3. Implementar retencao/arquivamento de auditoria.
4. Persistir extracoes por hash e mover trabalhos pesados para workers.
5. Modularizar backend e frontend gradualmente, mantendo os contratos atuais da API.
