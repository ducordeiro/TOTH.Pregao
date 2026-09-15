# Revisão do Bloco 7 em 12 de setembro de 2026

## Template

O PDF era produzido por uma composição independente em ReportLab e não recebia o template selecionado. Reiniciar o servidor, por si só, não resolveria essa causa. O DOCX usava o arquivo, mas acrescentava uma capa padrão e quebras de página.

A geração com template agora insere somente o conteúdo dos produtos. Um marcador `{CATALOGO}` isolado é substituído no próprio parágrafo, inclusive em tabelas; sem marcador, a inserção ocorre ao final, sem quebra de página artificial. Marcadores duplicados ou misturados a outros textos produzem uma mensagem explícita.

Os demais componentes do pacote Word são preservados byte a byte. O PDF é convertido a partir do DOCX gerado. Caso a conversão esteja indisponível, são disponibilizados Word e auditorias com um aviso; não é publicado um PDF de aparência diferente como se tivesse usado o template.

Teste com `C:/Users/ducor/OneDrive/Desktop/template-catalogo.docx`: logo, cabeçalho, estilos e numeração preservados; DOCX e PDF produzidos; PDF de uma página conferido visualmente. Geração e conversão: 8,13 segundos neste teste local. Campos vazios já existentes no modelo continuam vazios; não foram preenchidos com informações presumidas.

## Acervo consultado

A pasta `C:/Users/ducor/Downloads/relatoriocatalogogoldflex` não estava presente. O ZIP homônimo permanece em Downloads, e seus documentos importados estão em `data/catalog_repertoire/originals/`. O segundo caminho informado repete o primeiro.

Foram conferidos os hashes dos 169 documentos únicos importados. Foram extraídos textos de PDFs, parágrafos e tabelas Word, além dos relatórios previamente disponíveis:

- 167 documentos com texto extraído.
- 159 documentos consultáveis como repertório, excluindo requisitos de editais.
- Um TXT de pedido vazio e um edital digitalizado de três páginas sem texto extraível.
- Página registrada para PDFs; seção/parágrafo/tabela para Word; caminho e SHA-256 mantidos.

O inventário `validação de dados/validacao-modelos-cadeiras-por-categoria-v3.docx` lista 37 modelos documentais:

| Categoria | Modelos |
| --- | ---: |
| Cadeiras fixas | 13 |
| Cadeiras universitárias | 5 |
| Cadeiras com rodízios | 8 |
| Mochos | 3 |
| Poltronas de auditório | 8 |

Esses 37 registros são um inventário documental. Os seis perfis técnicos estruturados anteriores continuam distintos do inventário; a busca passou a alcançar também os PDFs e documentos Word dos demais produtos.

## Informações que exigem cuidado

O relatório consolidado NR-17 aponta 32 referências/configurações nos laudos e oito variantes com dimensões numéricas nos próprios laudos. Isso não significa que todas as demais dimensões estejam ausentes dos catálogos: por exemplo, o catálogo Chile Plus Size Maior acrescenta medidas que não estão no laudo da família.

Há diferenças entre dados de catálogo e laudo, como profundidade de assento de 39 cm no catálogo da universitária estofada e 40 cm no laudo da variante Secretaria. Não foram unificadas como se fossem a mesma configuração.

Quatro laudos históricos identificam Alpherflex. Sua associação à oferta Goldflex precisa de vínculo documental. Ensaios de espuma, metal e tecido permanecem específicos dos materiais/amostras descritos; não constituem aprovação universal da cadeira.

As menções históricas a tolerância de 5% ou configurações aceitas em pedidos anteriores não alteraram automaticamente as regras de atendimento do app. Os textos são referências rastreáveis para revisão.

## Respostas às pendências

Itens sem perfil estruturado passam a apresentar perguntas derivadas da especificação, em vez de somente um pedido genérico de cadastro. Itens com evidência parcial exibem os critérios pendentes e as confirmações técnicas já identificadas.

O usuário informa atendimento, especificação ofertada e evidência. Pode salvar parcialmente e continuar depois. As respostas são ligadas às perguntas recalculadas a partir do item atual; apagar ou alterar a lista de perguntas enviada pelo cliente não elimina pendências reais. As respostas anteriores permanecem reconhecidas ao completar as demais.

Uma resposta não confirmada ou divergente não encerra a pendência. As confirmações registradas pelo usuário permanecem identificadas na análise, com revisão humana obrigatória. Alterações nos requisitos exigem reanálise. A exportação persiste os itens revisados para que o próximo cadastro de respostas use a mesma especificação.

## Verificação

Testes cobrem preservação do template, marcador em tabela e dividido em runs, erro em marcadores ambíguos, conversão PDF a partir do DOCX, indisponibilidade do conversor, recuperação de referências com localização, exclusão de requisitos de editais, respostas parciais e completas, reanálise e perguntas de produtos sem perfil.

As verificações de interface usam o componente real em desktop e celular, com respostas de API controladas e a validação Python real. Não constituem uma nova consulta ao PNCP. A conferência do template usou conversão real pelo Word.

Para transportar o repertório, inclua `resources/catalog_library/references.json` e `data/catalog_repertoire/originals/`, além do banco e dos templates. O índice e as referências não são armazenados exclusivamente no SQLite.

### Resultado final e ativação

- Backend: 172 testes aprovados; última execução em 16,025 segundos.
- Frontend: 41 testes aprovados, build concluído e fluxo de perguntas/downloads verificado em desktop e celular.
- Template real: DOCX convertido pelo Word em PDF de uma página, em 8,13 segundos. Cabeçalho, imagem, estilos e numeração originais preservados no pacote DOCX.
- A reinicialização do servidor foi bloqueada pela revisão automática de permissões por limite de uso do Codex. O comando não foi executado: o backend em execução ainda precisa ser reiniciado para carregar as alterações. O processo de extração não foi interrompido.

Atualização posterior em 12/09, durante a verificação geral solicitada pelo usuário: a reinicialização foi autorizada e executada com sucesso. O novo servidor (PID 9304, porta 8765) carregou as alterações. A extração (PID 25000) foi preservada. Consulte `reports/verificacao-geral-2026-09-12.md` para resultados e limitações da auditoria operacional.
