# Bloco 7: estrutura tecnica e revisao das referencias

## Alteracoes de funcionamento

- Conteudo organizado em RESUMO DO ITEM, ASSENTO E ENCOSTO, ESTRUTURA METALICA / BASE, MECANISMOS E ACESSORIOS e OBSERVACOES.
- Identificacao com fabricante, CNPJ, numero do pregao, processo e orgao destinatario, conforme os dados recebidos. Campos ausentes permanecem a confirmar.
- Item, modelo, marca, cor, revestimento, carga, normas, materiais, dimensoes, tubos, solda, pintura, mecanismos, regulagens e garantia possuem campos ou pendencias explicitas.
- As cinco redacoes padrao solicitadas foram preservadas. Sem evidencia integral, aparecem identificadas como clausulas pendentes, nunca como certificacao automatica.
- As perguntas adicionais utilizam o formulario existente de resposta a pendencias. Corrigida a instabilidade que fazia perguntas reaparecerem na retomada de respostas parciais.
- O DOCX continua utilizando o template; o PDF com template continua sendo convertido desse mesmo DOCX. Arquivos, logotipos, cabecalhos, estilos e numeracao do template nao foram substituidos.
- Nao foram alterados nesta tarefa os blocos 1, 2 ou 4, a busca de oportunidades, o banco principal ou os extratores.

## Fontes consultadas

A pasta indicada em Downloads nao existe atualmente. Foi utilizado o arquivo `C:/Users/ducor/Downloads/relatoriocatalogogoldflex.zip`, alem das copias originais retidas pelo app.

O ZIP possui 8.207 arquivos, incluindo codigo e dependencias que nao foram tratados como catalogos nem executados. A conferencia incluiu SHA-256 dos documentos e leitura de texto por pagina, paragrafo ou tabela. Os quatro RAR e dois ZIP internos tambem foram conferidos: seus 202 documentos PDF/DOCX eram duplicados da biblioteca, exceto uma revisao alternativa do inventario, agora preservada separadamente.

Acervo final: 174 documentos unicos, 164 pesquisaveis como referencias, 37 modelos no inventario atual e seis perfis estruturados. Foram acrescentadas quatro analises da pasta analises e a revisao alternativa do inventario; nao foram substituidos perfis nem copiados limites entre modelos. A versao anterior do manifesto foi preservada em reports/catalog-library/references-before-*.json.

Foram localizadas referencias sobre compensado e fixacao, espuma e densidade, CFC, tubos e espessuras, solda MIG, pintura e estufa, normas, carga e garantia. O detalhamento com caminhos, paginas, trechos e hashes esta em reports/catalog-library/source-audit.json e source-audit.md.

Exemplos importantes da leitura:

- O laudo de espuma cita densidade de 45 a 55 e limita os resultados a amostra ensaiada. Isso nao autoriza aplicar os mesmos resultados a todas as espumas ou cadeiras.
- As analises UFRGS distinguem a versao estofada da versao em polipropileno. Carga e norma da primeira nao podem ser transferidas para a segunda.
- Algumas fontes identificam ALPHERFLEX como fabricante. O vinculo com o produto Goldflex ofertado precisa ser conferido.
- Existem referencias a solda MIG, processos anticorrosivos e normas, mas a existencia do documento nao identifica automaticamente o modelo/configuracao atendido.
- Permanecem um arquivo textual vazio e um edital digitalizado sem texto extraivel. Este edital nao e usado como evidencia do fabricante. A leitura textual nao substitui a revisao de desenhos, assinaturas, fotos e escopo dos laudos.

## Validacao

- 61 testes de catalogo, template, biblioteca, exportacao da proposta e estrutura DOCX passaram.
- Teste de navegador do Bloco 7 passou em desktop/celular, incluindo referencias, downloads, falha e nova tentativa, resposta parcial e retomada.
- Exportacao com template-catalogo.docx: Word e PDF em 8,32 segundos na ultima medicao; duas paginas conferidas visualmente, sem sobreposicoes. Partes do template preservadas por comparacao de bytes.
- Analise local de um item: 222,53 ms na primeira carga; media de 0,63 ms e p95 de 0,68 ms em 100 repeticoes com cache. Sao tempos da analise local, nao das consultas externas nem da conversao Word/PDF.
- Nenhuma API externa adicional foi introduzida. A biblioteca e lida localmente, com o cache ja existente.

Os dados do novo produto ainda nao foram fornecidos: o pedido continha um placeholder. Nao foi inventado um produto nem liberado um catalogo comercial como se estivesse validado. Para usar as alteracoes, atualizar a pagina, reanalisar o item, responder as pendencias aplicaveis e gerar novos arquivos.
