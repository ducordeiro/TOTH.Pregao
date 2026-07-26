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
