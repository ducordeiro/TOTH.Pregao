# Relatorio de correcoes cautelosas do importador

Data: 09/09/2026

## Estado da implementacao

As regras de correcao foram implementadas no importador e executadas em modo de simulacao. Nenhuma alteracao foi gravada no banco `data/pncp.sqlite3`.

Relatorio da simulacao: `data/relatorios_importacao/simulacao_20260909_011521_199992.json`.

## Regras aplicadas

- Duplicatas que apenas complementam campos foram unificadas, sem usar uma revisao antiga para sobrescrever a mais recente.
- Diferencas de espacos em branco foram tratadas como equivalentes; palavras, numeros e pontuacao diferentes continuam sendo conflito.
- Conflitos reais nao sao resolvidos por maioria ou escolha arbitraria: permanecem em revisao com os valores divergentes registrados.
- `id_comprasgov`, UASG e links invalidos sao omitidos quando nao podem ser comprovados; os dados PNCP consistentes permanecem preservados.
- Registros marcados como excluidos na fonte nao entram na proposta automatica.
- O preenchimento proposto altera somente colunas que estao nulas ou vazias no registro existente.

## Resultado comparativo

| Indicador | Simulacao anterior | Simulacao atual |
|---|---:|---:|
| Grupos para revisao | 1.479 | 350 |
| Linhas para revisao | 4.093 | 942 |
| Novas propostas | 30.548 | 31.658 |
| Atualizacoes propostas | 25.527 | 25.539 |

Foram recuperados 1.129 grupos que antes estavam bloqueados por duplicidades trataveis. A simulacao atual analisou 95.590 linhas, agrupadas em 63.922 oportunidades, e terminou em 56,215 segundos.

## Grupos ainda pendentes

- 328 grupos: duplicidades com conflito real na mesma data de atualizacao. Recomenda-se consultar a linha mais recente no arquivo oficial ou na origem do processo e corrigir a origem antes de importar.
- 21 grupos: contratacoes marcadas como excluidas na fonte. Recomenda-se manter fora do banco ate confirmar uma republicacao ou reversao oficial.
- 1 grupo: numero de controle PNCP ausente ou invalido. Recomenda-se obter a chave oficial; nao e seguro inventar ou inferir a identificacao.

## Proxima etapa segura

Revisar os 350 grupos do JSONL detalhado, anexar evidencia oficial aos conflitos e somente entao executar uma etapa de aplicacao transacional com backup, contagem antes/depois e validacao de integridade. A simulacao atual nao baixa itens, nao atualiza indices e nao modifica o banco.
