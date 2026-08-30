# TOTH Propostas

Aplicacao para consultar editais do PNCP, extrair itens dos arquivos oficiais e
gerar propostas comerciais em Word.

## Arquitetura

- `server.py`: backend HTTP em Python, extracao de documentos e geracao Word.
- `frontend/`: interface React 19 escrita em TypeScript e compilada com Vite.
- `frontend_dist/`: build de producao servido pelo backend Python.
- `data/pncp.sqlite3`: banco SQLite com responsaveis, vinculos e cache de itens.
- `templates/`: templates Word cadastrados.
- `uploads/` e `outputs/`: arquivos temporarios e documentos gerados.

O frontend consome os endpoints do servidor Python. A interface React fica em
`/`; a interface HTML anterior permanece disponivel em `/legacy` como
contingencia. Se `frontend_dist/index.html` nao existir, o servidor usa
automaticamente a interface anterior.

## Executar

Na pasta `Pregao`, execute:

```powershell
.\iniciar_aplicacao_web.cmd
```

A aplicacao abre em `http://127.0.0.1:8765`.

## Atualizar o frontend

```powershell
cd .\ocr_edital_web\frontend
npm install
npm run typecheck
npm test -- --run
npm run build
```

O build e gravado em `ocr_edital_web/frontend_dist` e passa a ser servido pelo
Python sem mudar os contratos da API ou o banco SQLite.

## Testar o backend

```powershell
cd .\ocr_edital_web
python -m unittest -v
```

## Radar ETL

O Bloco 1 consulta as oportunidades normalizadas no SQLite. As coletas do PNCP
e do Compras.gov ficam isoladas em `etl/`, com auditoria do JSON bruto nas
tabelas criadas por `migrations/001_create_opportunity_radar_tables.sql`.

Executar uma carga diaria limitada:

```powershell
cd .\ocr_edital_web
python -m etl daily --date 2026-08-05 --modality-code 6 --max-pages 2 --max-records 100
```

Validar sem gravar oportunidades ou payloads:

```powershell
python -m etl daily --dry-run --max-pages 1 --max-records 10
```

Coletar atualizacoes ou a fonte complementar:

```powershell
python -m etl update --date-from 2026-08-05 --date-to 2026-08-05 --modality-code 6
python -m etl compras --max-pages 1 --max-records 50 --filters-json '{"dataPublicacaoPncpInicial":"2026-08-05","dataPublicacaoPncpFinal":"2026-08-05","codigoModalidade":6}'
```

Rotas internas principais:

- `GET /internal/opportunities`
- `GET /internal/opportunities/{id}`
- `POST /internal/opportunities/{id}/ignore`
- `POST /internal/opportunities/{id}/convert-to-proposal`
- `GET /internal/etl/runs`
- `POST /internal/etl/pncp-sync`

Defina `TOTH_ETL_ADMIN_TOKEN` para exigir o cabecalho `X-ETL-Token` na
sincronizacao manual exposta pelo servidor.

### Completar itens para a busca por produto

O coletor em lote do Compras.gov deve ser executado primeiro. Ele recebe ate
500 itens por pagina, consolida estados duplicados e pode ser retomado pelo
arquivo de status:

```powershell
cd .\ocr_edital_web
python .\scripts\bulk_enrich_comprasgov_items.py `
  --database .\data\pncp.sqlite3 `
  --date-from 2026-06-01 `
  --date-to 2026-08-25 `
  --stored-source all
```

Depois, o coletor individual completa oportunidades que nao aparecem no lote
do Compras.gov. Ele consulta somente registros ainda sem itens e prioriza
oportunidades abertas e futuras:

```powershell
python .\scripts\enrich_missing_pncp_items.py `
  --database .\data\pncp.sqlite3 `
  --date-from 2026-06-01 `
  --scope publication `
  --source all
```

O andamento fica em `data/comprasgov_items_bulk.status.json` e
`data/items_enrichment_priority.status.json`. Os arquivos registram pagina,
contadores, falhas, velocidade e estimativa de conclusao.

Para priorizar um dia de encerramento especifico sem interromper a fila geral:

```powershell
python .\scripts\enrich_missing_pncp_items.py `
  --database .\data\pncp.sqlite3 `
  --scope closing `
  --date-from 2026-08-24 `
  --date-to 2026-08-24 `
  --item-page-size 500
```
