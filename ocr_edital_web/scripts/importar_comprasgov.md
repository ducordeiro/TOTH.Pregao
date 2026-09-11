# Simulacao da importacao Compras.gov

Execute na pasta `ocr_edital_web`:

```powershell
python scripts\importar_comprasgov.py --simular
```

Se `python` nao estiver disponivel no terminal:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts\importar_comprasgov.py --simular
```

O banco padrao e `data/pncp.sqlite3`, com origem em `comprasGOV_organizado`.
Parametros opcionais: `--banco CAMINHO`, `--tabela NOME`, `--relatorios PASTA`.

No modo `--simular`, a conexao usa `mode=ro` e `PRAGMA query_only=ON`. Nenhuma tabela, indice,
classificacao ou historico ETL e alterado. Nao ha chamadas de rede.
O unico conteudo criado sao os relatorios, fora do arquivo SQLite.

## Relatorios

- `.json`: totais, lacunas por coluna e motivos para revisao.
- `.jsonl`: uma decisao por chave, com os campos propostos, divergencias
  preservadas e avisos. Pode ser lido linha a linha mesmo sendo grande.

As chaves PNCP sao conferidas contra CNPJ, ano e sequencial. A correspondencia
usa `external_key` e `pncp_control_number`, sem depender de semelhanca do objeto.
Entre duplicatas, a data de atualizacao mais recente tem prioridade. Empates
com campos normalizados diferentes e datas ambiguas exigem revisao.
O campo `codigo_modalidade` nao e usado para a modalidade PNCP; usa-se
`modalidade_id_pncp`. Identificadores Compras.gov divergentes do link sao omitidos.
Zero e valor preenchido: nao e tratado como lacuna.

Na versao 2 das regras, revisoes com fuso sao comparadas pelo instante real.
Revisoes que misturam datas com e sem fuso exigem revisao. O periodo tambem e
validado depois de combinar as lacunas com as datas ja existentes no destino.
Identidades PNCP divergentes no destino bloqueiam a proposta de atualizacao.
IDs Compras.gov sao conferidos contra UASG, numero da compra, link e associacoes
a outras oportunidades. O campo e omitido quando a associacao e ambigua.
No destino, somente NULL e texto em branco sao lacunas; o texto literal `null`
e preservado. Valores numericos nao finitos ou que excedem REAL sao recusados.
Os relatorios incluem a versao das regras e a duracao da analise.

## Recuperacao cautelosa (versao 3)

- Duplicatas da mesma revisao podem complementar campos vazios. Valores
  preenchidos diferentes continuam exigindo revisao. Nao se usa a maioria.
- Espacos repetidos sao equivalentes nos campos de texto; palavras, numeros,
  acentos e pontuacao continuam significativos.
- Datas complementadas sao validadas em conjunto; dados de revisoes antigas
  nao preenchem lacunas de uma revisao recente automaticamente.
- Link de origem ou UASG invalidos sao omitidos com aviso, junto ao ID Compras.gov
  dependente dessa verificacao. A identidade PNCP precisa continuar valida.
  A pagina PNCP e montada a partir do CNPJ, ano e sequencial conferidos, sem
  presumir que a pagina esteja disponivel online.
- Conflitos apenas no ID Compras.gov omitem esse campo. Conflitos no objeto,
  valores, datas e demais campos essenciais mantem o grupo separado.
- O JSONL informa campos e valores conflitantes para orientar a verificacao
  posterior no PNCP/documento oficial. Nenhum valor e escolhido por semelhanca.
- Contratacoes excluidas permanecem separadas; nao devem ser reativadas por
  importacao. Chaves ausentes precisam de identificacao comprovada na origem.

Avisos de campos omitidos precisam ser revisados mesmo quando o restante da
oportunidade consta como inclusao ou preenchimento proposto. As tabelas de
origem e destino continuam intactas no modo de simulacao.

## Aplicacao

Na versao 4, descricoes da mesma revisao que diferem somente por aspas
simples/duplas e espacos sao equivalentes. Prevalece a versao original com
mais aspas duplas, com desempate deterministico pelo texto. O conteudo nao e
reescrito: apostrofos sao preservados. A regra vale apenas para `description`;
palavras, numeros e outros sinais diferentes continuam bloqueando o grupo.
Campos ja preenchidos no destino continuam preservados.

Execute `python scripts/importar_comprasgov.py --aplicar` para gravar.
O comando bloqueia outras escritas temporariamente, cria um backup SQLite em
`data/backups_importacao`, verifica sua integridade e recalcula o plano sobre
essa copia consistente. As inclusoes e preenchimentos sao gravados em uma
transacao; os gatilhos existentes do Toth atualizam o indice de busca.
Campos preenchidos sao preservados e grupos em revisao sao ignorados.
Uma falha antes do commit desfaz a transacao. O relatorio `aplicacao_*.json`
registra as contagens efetivas e o caminho do backup. Nenhum item e baixado.
Nao execute o JSONL como SQL nem importe-o diretamente.

Os totais sao propostas preliminares, e nao comprovam disponibilidade dos itens.
O script compara textos literalmente (exceto datas normalizadas), de modo que
uma divergencia pode ser apenas uma diferenca de grafia. Nada e sobrescrito.

Teste:

```powershell
python -m unittest discover -s scripts -p test_importar_comprasgov.py -v
```
