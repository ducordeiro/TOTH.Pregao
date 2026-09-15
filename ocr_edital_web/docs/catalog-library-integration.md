# Biblioteca complementar do Bloco 7

## Origem e deduplicacao

Foram comparados por SHA-256 os 182 arquivos de `Modelos de catalogos (1).zip`
com a pasta homonima em `relatoriocatalogogoldflex.zip`: todos sao identicos.
O segundo pacote inclui tambem codigo, instrucoes editoriais, dependencias e
arquivos temporarios. Nenhum script, prompt ou AGENTS.md do pacote foi executado
ou instalado como instrucao do aplicativo.

A importacao selecionou documentos MD, TXT, PDF e DOCX, deduplicando por hash:
169 referencias unicas, com 62 relatorios textuais pesquisaveis. Pedidos de
edital explicitamente identificados ficam fora da recuperacao de referencias.
Os demais documentos historicos ainda podem conter requisitos e conclusoes;
por isso nenhum trecho recuperado constitui aprovacao automatica.

## Analise tecnica do material

- O acervo separa modelo, configuracao, ensaio de componente e exigencia do edital.
- Espuma: existem mapeamentos de densidade, queima, resiliencia, compressao,
  fadiga, tracao e CFC; resultados pertencem as amostras e metodos documentados.
- Tecido: o relatorio consolidado distingue a identificacao "100% poliester"
  dos ensaios efetivamente realizados. Nao assumir ensaio de composicao.
- Componentes metalicos e ergonomia possuem mapeamentos independentes. Nao
  transferir automaticamente um resultado para outra cadeira ou configuracao.
- As regras narrativas restringem tolerancia de 5% aos processos que a autorizam.
  O valor isolado no JSON nao deve se tornar tolerancia global.
- Os indicadores de garantia e bracos configuraveis do pacote nao bastam para
  provar qualquer prazo de garantia ou qualquer configuracao de produto.
- O validador fornecido verifica termos/tabelas de arquivos v2 e pode imprimir
  aprovacao mesmo encontrando zero arquivos. Nao foi adotado como certificacao.
- O pacote cita template editorial v4; a integracao preserva o template escolhido
  pelo usuario e as regras A4 vertical existentes, sem substituir modelos.

Esta etapa avaliou inventario, hashes, arquitetura, regras, estrutura de dados e
relatorios selecionados. Nao representa pericia ou revisao visual integral de
todos os PDFs e DOCX nem verificacao externa da validade de normas/laudos.

## Integracao implementada

`catalog_library.py` recupera ate cinco referencias por item usando termos
normalizados, relevancia documental e um filtro de familia de mobiliario.
O indice e mantido em memoria; consultas repetidas utilizam cache limitado.
Cada resultado inclui documento, trecho, SHA-256 e estado referencia_para_revisao.

O Bloco 7 apresenta as referencias em uma secao expansivel separada da conclusao
de aderencia. O JSON de auditoria exportado conserva esses resultados. Ao editar
um requisito, referencias antigas ficam ocultas ate a reanalise.

Continuam seis perfis comerciais estruturados: esta etapa amplia a biblioteca
consultavel, nao converte automaticamente 169 documentos em novos modelos.
As referencias nao alteram a capacidade, medida, garantia, norma ou estado de
aprovacao dos perfis existentes e nao sao copiadas para o catalogo comercial.

## Arquivos para levar a outro computador

- Codigo do Bloco 7 e `resources/catalog_library/references.json`.
- `data/catalog_repertoire/originals/`: originais preservados e nomeados por hash.
  Essa pasta fica fora do Git pelas regras de dados do projeto.
- Banco principal e templates do app, conforme o procedimento de backup.

A biblioteca nao esta embutida no SQLite. Exportar somente o banco nao leva os
originais desta biblioteca. O script `scripts/import_catalog_library.py` permite
reproduzir a importacao a partir do ZIP completo, sem executar seu conteudo.

## Validacoes desta entrega

- 15 testes Python de regras, biblioteca, deduplicacao, recuperacao, isolamento
  de resultados, exportacao de auditoria e bloqueio de alegacoes automaticas.
- 41 testes frontend; compilacao TypeScript e build de producao aprovados.
- Playwright com o componente real do Bloco 7 e respostas de API simuladas
  geradas pelo backend: exibicao de cinco referencias e viewport desktop/mobile.
- Todos os 169 originais locais conferidos contra os hashes do manifesto.
- Exemplo medido: primeira recuperacao 175,42 ms; repeticao em cache 0,004 ms.
  Esses tempos sao locais e nao medem o processamento completo de um edital.
