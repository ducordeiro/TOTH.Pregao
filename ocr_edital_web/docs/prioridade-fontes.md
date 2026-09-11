# Prioridade das fontes online

O banco local continua atendendo primeiro. A atualizacao em segundo plano e o
preenchimento de detalhes/itens ausentes tentam Compras.gov antes do PNCP.

Documentacao oficial consultada: https://dadosabertos.compras.gov.br/v3/api-docs

## Recursos

- Contratacao: `/modulo-contratacoes/1.1_consultarContratacoes_PNCP_14133_Id`.
- Itens: `/modulo-contratacoes/2.1_consultarItensContratacoes_PNCP_14133_Id`.
- Publicacoes: `/modulo-contratacoes/1_consultarContratacoes_PNCP_14133`.
- Identificacao: `tipo=numeroControlePNCPCompra&codigo=CNPJ-1-SEQUENCIAL/ANO`.
- Anexos: permanecem no PNCP, pois o modulo documentado nao oferece esse recurso.

## Protecoes

- Timeout Compras.gov de 4 segundos, sem repeticoes antes do fallback.
- Falha de transporte ou formato invalido coloca apenas aquele endpoint em espera
  por 30 segundos; outros endpoints continuam disponiveis.
- Resposta vazia, truncada, duplicada ou de outra contratacao aciona o PNCP.
- Paginas sao conferidas pelo total informado, nao pelo tamanho da ultima pagina.
- Itens de uma resposta parcial nao substituem os itens locais.
- URLs de origem permanecem na auditoria; a chave de negocio continua sendo PNCP,
  evitando duplicar uma contratacao quando se troca o provedor.

## Limites de equivalencia

Os codigos de modalidade nao sao iguais. Equivalencias validadas por amostras
oficiais: PNCP 6 (pregao eletronico) -> Compras.gov 5;
PNCP 8 (dispensa) -> Compras.gov 6. Outras modalidades usam PNCP ate que sua
equivalencia seja validada. Uma busca sem modalidade tambem recebe complemento PNCP.

Compras.gov filtra publicacao, nao abertura/encerramento. Nessas buscas, o app
atualiza publicacoes recentes pelo Compras.gov e recorre ao PNCP para complementar
o periodo original. Busca por palavra-chave/tipo de objeto tambem recebe complemento
PNCP para nao declarar cobertura de itens ainda nao indexados.

A busca interativa permite ate 12 segundos de processamento Compras.gov, mais a
requisicao em curso (ate 4 segundos), antes de recorrer ao PNCP. O banco continua
visivel nesse intervalo. O limite de paginacao gera fallback, nunca sucesso completo.

## Verificacao

`python -m unittest test_preferred_source -q` cobre prioridade, falhas, identidade,
paginacao, modalidades, preservacao de descricoes e integracao em SQLite temporario.
Os testes nao importam dados de exemplo para o banco de producao.
