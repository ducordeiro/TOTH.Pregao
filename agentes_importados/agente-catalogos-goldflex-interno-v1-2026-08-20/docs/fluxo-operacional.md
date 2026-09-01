# Fluxo operacional

## Entradas

- PDF do catálogo a avaliar.
- Modelo/referência visual aprovado, quando aplicável.
- Ficha técnica, desenhos ou planilha de origem, quando disponíveis.
- Identificador do caso, versão, data e responsável.

## Etapas

1. **Inventário:** registrar páginas, produtos, anexos e qualidade/legibilidade do PDF.
2. **Leitura visual:** descrever grade, hierarquia, tipografia, cores, imagens, tabelas, consistência e desvios em relação ao modelo.
3. **Identificação:** classificar família e variante somente com base no texto/imagem; para cadeiras, distinguir, por exemplo, assento estofado e assento injetado apenas quando houver evidência.
4. **Extração técnica:** capturar medidas, componentes, materiais, acabamentos, mecanismos, códigos e opções, sempre com fonte.
5. **Checagem:** comparar valores repetidos, detectar conflitos entre páginas e separar fato, leitura visual e hipótese.
6. **Normalização:** produzir níveis básico, intermediário e completo, mantendo o campo original e o valor normalizado.
7. **Criação orientada:** preencher um novo catálogo somente a partir da referência aprovada e da ficha técnica validada.
8. **Revisão final:** comparar novo PDF com ficha e padrão visual; emitir aprovado, aprovado com pendências ou reprovado.

## Estados de evidência

| Estado | Uso |
|---|---|
| `confirmado` | Texto/tabela legível ou imagem inequívoca, com página/região. |
| `visual_indicado` | Aparência sugere algo, mas não prova especificação. |
| `nao_comprovado` | O campo foi procurado, mas não há evidência suficiente. |
| `ausente` | Campo esperado não aparece no material consultado. |
| `a_confirmar` | Divergência, baixa resolução ou dado que requer fonte externa. |

Nunca converter `visual_indicado` em `confirmado`.

## Critérios de aprovação

- Todos os produtos têm código/nome rastreável ou pendência explícita.
- Cada medida e característica técnica tem fonte ou estado de ausência.
- Não existem conflitos sem resolução entre ficha, texto e tabela.
- O PDF novo preserva o modelo aprovado em hierarquia, grid, margens, tipografia, cores e tratamento de imagens.
- Campos críticos pendentes estão listados com responsável sugerido e ação de confirmação.
