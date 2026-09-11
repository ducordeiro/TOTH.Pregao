# Auditoria do importador Compras.gov

Escopo: script de simulacao e seus testes. A base foi aberta somente para leitura.
A etapa de aplicacao continua desabilitada e nao foi testada nem executada.

## Problemas corrigidos

- Revisoes com fusos diferentes eram ordenadas como texto. Agora a comparacao
  usa instantes; misturas ambiguas de datas com e sem fuso exigem revisao.
- Marcadores de exclusao/inatividade com espacos podiam passar. Agora sao
  normalizados antes de decidir se a linha pode ser utilizada.
- O periodo proposto podia contradizer uma data preenchida no destino. Agora
  o resultado combinado e validado antes de propor a atualizacao.
- Um ID Compras.gov podia ser associado a varias chaves PNCP. Agora colisoes
  na origem e no destino impedem o preenchimento desse identificador.
- Identificadores passam por verificacao adicional de UASG e numero da compra.
- A identidade do destino e conferida antes de preencher suas lacunas.
- Texto literal `null` no destino era considerado vazio. Agora apenas NULL e
  texto em branco sao lacunas. Zero continua preservado.
- Valores estimados que excedem REAL e UASGs fora do formato sao recusados.
- Agrupamento e ordenacao usam a mesma normalizacao da chave.
- Revisoes pendentes agora incluem referencias aos registros da origem.

## Evidencias

18 testes aprovados. Incluem datas, duplicidades, preservacao de zero, rejeicao
de exclusoes, conflitos de identidade, IDs ambiguos e hash identico do banco de
teste antes/depois da simulacao. Banco real: conexao mode=ro e query_only=ON.

Simulacao completa: 95.590 linhas, 63.922 grupos, 98,78 segundos.

| Decisao | Quantidade |
| --- | ---: |
| Novas oportunidades propostas | 30.548 |
| Existentes com lacunas preenchiveis | 25.527 |
| Existentes preservadas sem preenchimento | 6.368 |
| Grupos para revisao | 1.479 |

Validacao independente do JSONL confirmou: uma decisao por chave, totais
consistentes, nenhum ID Compras.gov repetido entre as propostas de preenchimento
e inclusao, e todos os 44.073 campos propostos estavam vazios no destino.

## Pendencias de dados

1.414 grupos com duplicidades conflitantes na mesma data; 21 marcados como
excluidos; 42 com link invalido; um com UASG invalida; um grupo sem chave valida.
Os grupos para revisao totalizam 4.093 linhas.

26.634 grupos omitiram id_compra por formato ou divergencia com link/UASG/numero;
274 omitiram esse campo por associacao a outras oportunidades. Esses avisos
nao impedem outros campos de serem considerados quando a identidade PNCP valida
permite o relacionamento. Nenhum identificador foi inventado ou corrigido por
aproximacao.

Relatorio detalhado: data/relatorios_importacao/simulacao_20260909_010558_855799.jsonl
Resumo: data/relatorios_importacao/simulacao_20260909_010558_855799.json

## Limites

Conclusao: o simulador tem cobertura adequada para as regras revisadas. O plano
nao e uma importacao aplicada. Antes de implementar a gravacao, sera necessario
integrar backup consistente, persistencia do Toth, auditoria de alteracoes e
atualizacao das classificacoes e indices. Dados da fonte podem mudar, portanto
a simulacao deve ser repetida antes de qualquer aplicacao. Este trabalho nao
valida disponibilidade de itens nem documentos pela API.
