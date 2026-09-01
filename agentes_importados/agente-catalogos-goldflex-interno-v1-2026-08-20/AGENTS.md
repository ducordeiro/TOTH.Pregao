# AGENTS.md — Catálogos Técnicos Goldflex

## Finalidade

Este arquivo contém as regras permanentes de funcionamento dos agentes que trabalham neste projeto. Elas foram consolidadas durante sucessivas análises, correções, validações e aprovações de catálogos técnicos.

Estas regras são importantes porque os documentos produzidos podem passar por revisão técnica externa. Um catálogo visualmente bem apresentado, mas tecnicamente inconsistente, pode comprometer a identificação do modelo. Da mesma forma, uma alteração editorial não autorizada pode descaracterizar uma construção já aprovada.

Todo agente deve ler este arquivo antes de analisar PDFs, criar laudos, atualizar a biblioteca de modelos ou gerar documentos Word/PDF.

## Escopo

As instruções deste arquivo aplicam-se a todo o projeto `relatoriocatalogogoldflex`, inclusive:

- catálogos originais em PDF;
- laudos e relatórios técnicos;
- biblioteca de modelos;
- arquivos Word e Excel;
- scripts Python de geração e validação;
- modelos editoriais e arquivos de configuração.

## Princípio central

Cada informação publicada deve ter origem em pelo menos uma destas fontes:

1. catálogo ou PDF analisado;
2. laudo técnico produzido a partir do catálogo;
3. confirmação expressa do fabricante registrada no projeto;
4. ficha técnica, desenho, ensaio ou documento formal incorporado ao caso.

Nunca transformar ausência de informação, inferência visual ou semelhança entre produtos em fato confirmado.

## Modelo editorial oficial

O padrão editorial oficial é a **versão 4**.

Referência principal:

`Modelos de catalogos/catalogos de pedidos/dados extraidos/dados extraidos versao 3/catalogo-goldflex-mocho-ergonomico-bipartido-estancia-velha-v4.docx`

Os próximos catálogos devem preservar:

- logotipo Goldflex;
- cor institucional `#FFC000`;
- cabeçalho institucional;
- hierarquia tipográfica;
- tabelas técnicas;
- organização por blocos;
- espaçamentos e linha visual aprovados.

O modelo Word aprovado deve ser copiado para uma nova versão. Nunca alterar diretamente o arquivo usado como referência.

## Identificação institucional obrigatória

Usar sempre como fabricante:

**GOLDFLEX INDUSTRIA E COMERCIO DE MOVEIS E EQUIPAMENTOS LTDA CNPJ 33.661.439/0001-14**

Não substituir essa identificação por fabricante encontrado em catálogo histórico, salvo ordem expressa do usuário para um documento específico.

## Regras obrigatórias dos catálogos

1. Cada catálogo deve representar um **modelo técnico permanente de cadeira**, e não um pedido, órgão ou edital específico.
2. O título da seção principal deve ser somente **Características**.
3. Usar nomes oficiais e tecnicamente claros para o modelo e sua categoria construtiva.
4. Separar identificação, características, medidas, estrutura, materiais, acabamentos, capacidade e normas quando houver conteúdo comprovado.
5. Publicar medidas com unidade e orientação: altura, largura, profundidade, espessura, diâmetro ou curso.
6. Não arredondar, converter ou corrigir números sem conservar o valor de origem.
7. Não completar cor, densidade, norma, capacidade, material, mecanismo ou acabamento por suposição.
8. Não publicar prompts, regras internas, instruções de produção ou comentários do agente.
9. Não inserir informações adicionais apenas para preencher espaço.
10. A quantidade de conteúdo deve acompanhar a quantidade de evidência disponível para o modelo.

## Conteúdos proibidos em catálogos

Não usar, salvo solicitação expressa do usuário:

- `Características do modelo-base comprovadas no catálogo`;
- `Configuração ofertada para este pedido`;
- `Atendimento documental e validação da configuração`;
- `Nota de apresentação ao pregoeiro`;
- textos dirigidos a pregoeiro, comissão, órgão comprador ou supervisão externa;
- menções a estratégia de licitação, aceitação, proposta ou disputa;
- instruções para fabricar, adaptar ou comprovar o produto;
- comparação entre o catálogo e um edital.

O contexto de pregão explica o nível de cuidado necessário, mas não é conteúdo automático do catálogo.

## Catálogos genéricos e configurações

- Catálogos são genéricos por modelo.
- Variações de tecido, cor, braços, dimensões e acabamentos podem integrar a família do modelo quando confirmadas pelo fabricante.
- Essas variações devem ser registradas de forma técnica e neutra, sem vincular o catálogo a um pedido específico.
- O catálogo-base funciona como trava de segurança para identificar a construção disponível.
- Não alterar um catálogo histórico para fazê-lo parecer compatível com um requisito posterior.

## Premissas confirmadas pelo fabricante

- Braços são acessórios independentes: um modelo pode ser configurado com ou sem braços.
- A garantia pode ser oferecida conforme o prazo solicitado, devendo ser formalizada no documento comercial ou técnico aplicável.
- O fabricante pode trabalhar com diferentes tecidos, cores, medidas, acabamentos, laudos e ensaios, desde que a configuração seja registrada e tecnicamente sustentada.
- Confirmação do fabricante e evidência impressa no catálogo são fontes diferentes e devem permanecer distinguíveis nos laudos e relatórios.

## Medidas e tolerâncias

- Comparações podem considerar tolerância de até 5%.
- Sempre informar a diferença absoluta e percentual quando duas medidas forem comparadas.
- Medidas acima de um mínimo podem ser favoráveis, mas não representam aceitação automática.
- Medidas abaixo do mínimo não devem ser declaradas conformes apenas pela tolerância interna.
- Se a ordem das cotas estiver ambígua, registrar a dúvida e não escolher uma interpretação silenciosamente.

## Laudos e relatórios

Os laudos devem:

- identificar todos os documentos analisados;
- registrar modelo, categoria e tipo de movimento;
- extrair medidas, materiais, componentes, acabamentos e regulagens;
- indicar arquivo e página da evidência;
- distinguir comprovado, confirmado pelo fabricante, não evidenciado e conflitante;
- listar lacunas sem transformar ausência em reprovação automática;
- preservar a diferença entre catálogo, laudo, ensaio, certificado, amostra e declaração.

Relatórios comparativos podem tratar de requisitos de pedidos ou editais. Catálogos comerciais/técnicos não devem conter essa comparação.

## Normas, laudos e ensaios

- Uma norma citada em catálogo não equivale a um certificado revisado.
- Não afirmar que um laudo ou ensaio foi examinado quando o arquivo não estiver disponível.
- Quando o usuário confirmar histórico de aprovação, tratar isso como premissa fornecida pelo usuário, não como verificação independente.
- Registrar quais laudos, ensaios ou documentos devem acompanhar a configuração quando forem exigidos.

## Fluxo obrigatório de trabalho

1. Inspecionar a pasta e preservar os arquivos existentes.
2. Identificar PDF, laudo, ficha, confirmação e modelo Word aplicáveis.
3. Extrair o conteúdo com rastreabilidade por página.
4. Classificar o modelo sem fundir produtos apenas semelhantes.
5. Normalizar medidas, materiais e componentes.
6. Montar o documento usando o padrão V4.
7. Alterar somente os elementos necessários para o modelo atual.
8. Validar o DOCX estruturalmente e, quando disponível, visualmente.
9. Verificar termos proibidos e fabricante padronizado.
10. Informar exatamente o arquivo criado, o caminho e o resultado da validação.

## Conduta de desenvolvimento de software

O agente também atua como desenvolvedor de software cauteloso:

- usar scripts reutilizáveis para tarefas repetidas;
- usar `apply_patch` para editar arquivos de projeto;
- preservar alterações do usuário;
- não sobrescrever versões aprovadas sem autorização;
- evitar comandos destrutivos;
- validar caminhos antes de copiar, mover ou excluir;
- gerar nova versão quando a mudança for material;
- verificar se arquivos Word abrem e contêm as seções esperadas;
- manter regras, dados técnicos e apresentação visual em camadas separadas;
- não introduzir alterações fora do escopo solicitado.

## Biblioteca e classificação dos modelos

O registro consolidado deve ser atualizado sem duplicar modelos comprovadamente iguais.

Documento atual de classificação:

`Modelos de catalogos/validação de dados/validacao-modelos-cadeiras-por-categoria-v3.docx`

Categorias principais:

- cadeiras fixas;
- cadeiras universitárias;
- cadeiras com rodízios;
- mochos;
- poltronas de auditório.

Modelos apenas parecidos não devem ser fundidos sem evidência técnica suficiente.

## Catálogos utilizados como referência

As pastas abaixo formam a biblioteca documental de referência. O agente deve consultar o catálogo e o laudo correspondente ao modelo, evitando transportar características de uma cadeira para outra.

### Pastas de referência já analisadas

- `Catalogo cadeira - Assistencia Juridica`
- `catalogo cadeira - Paranagua`
- `Catalogo cadeira - Piçarras`
- `Catalogo cadeira Almirante Alexandrino`
- `Catalogo cadeira Material Belico injetada`
- `Catalogo cadeira Patrocinio Paulista`
- `Catalogo cadeira Sj dos Pinhais`
- `Catalogo cadeira UFRGS`
- `catalogo cadeiras - Artilharia`
- `catalogo cadeiras - Bombeiros`
- `catalogo cadeiras - Del Rei`
- `catalogo cadeiras - Embrapa`
- `catalogo cadeiras - Estancia velha`
- `catalogo cadeiras - Lagoa Santa 12`
- `catalogo cadeiras - Lagoa Santa 33`
- `catalogo cadeiras - Material Belico Tela`
- `catalogo cadeiras - Piumhi`
- `catalogo cadeiras - Prefeitura BH`
- `catalogo cadeiras - Pro-reitoria`
- `catalogo cadeiras - Sao Roque 9`
- `catalogo cadeiras - Secretaria Seguranca Publica`
- `catalogo cadeiras - Tijucas`
- `catalogo cadeiras - unitau`
- `catalogo cadeiras - USP 90015`
- `catalogo cadeiras CRECI`
- `catalogo cadeiras Londrina auditorio`
- `catalogo cadeiras Prefeitura BH universitaria`

### Catálogos da pasta `Catalogos geral`

- `ITEM 1 - CADEIRA DIRETOR FIXA.pdf`
- `ITEM 1 - POLTRONA FIXA COM BRACOS.pdf`
- `ITEM 12 e 13 - POLTRONA DE AUDITORIO DE 01 LUGAR.pdf`
- `ITEM 14 - MOCHO ODONTOLOGICO BIPARTIDO.pdf`
- `ITEM 15 - Cadeira Giratória Modelo Diretor Cromada.pdf`
- `ITEM 2 – CADEIRA FIXA PARA ATENDIMENTO ADMINISTRATIVO.pdf`
- `ITEM 24 - POLTRONA AUDITORIO.pdf`
- `ITEM 4 - CADEIRAS FIXAS PARA SALAS DE AULA.pdf`
- `ITEM 6 - CADEIRA GIRATORIA CAPACIDADE 140KG.pdf`
- `ITEM 8  Poltrona de Espera sem Bracos.pdf`
- `ITEM 9  Poltrona para Auditorio com Prancheta Lateral Rebativel.pdf`

### Documentos editoriais de referência

- catálogo oficial V4 do Mocho Ergonômico Bipartido;
- catálogo V4 da Cadeira Executiva Lâmina Ergonômica;
- laudos técnicos consolidados nas pastas dos catálogos;
- arquivo `config/modelo-aprovado-goldflex.json`;
- prompt `prompts/07-agente-editorial-catalogo.md`;
- arquitetura `docs/arquitetura-agente-editorial-catalogo.md`.

## Regra final

Quando houver conflito entre aparência e precisão técnica, preservar a precisão técnica. Quando houver dúvida entre alterar e preservar, preservar o documento aprovado e registrar a dúvida. Quando faltar evidência, não inventar.
