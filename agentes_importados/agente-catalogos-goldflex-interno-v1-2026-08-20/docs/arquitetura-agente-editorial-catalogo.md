# Arquitetura do agente de editoração de catálogos

## Objetivo

Gerar catálogos Goldflex consistentes, tecnicamente rastreáveis e visualmente alinhados ao modelo Word aprovado, sem transformar hipótese em especificação.

O modelo editorial atualmente aprovado é `Mocho Ergonômico Bipartido — Estância Velha — versão 4`. Novos catálogos devem manter sua linha visual, organização das informações, uso do logotipo, cor de marca `#FFC000` e separação entre dados do catálogo-base e confirmações posteriores do fabricante.

## Fluxo de produção

```text
PDF + laudo aplicado
        ↓
Extração estruturada (Python)
        ↓
Normalização e comparação de medidas (regra de ±5%)
        ↓
Agente de editoração (regras e redação)
        ↓
Montagem DOCX baseada no modelo aprovado
        ↓
Validação automática + revisão visual
        ↓
Catálogo liberado / pendência para confirmação
```

## Responsabilidade de cada camada

### 1. Python — preparação e controle

- localiza o PDF, laudo e modelo Word;
- extrai títulos, tabelas, medidas, materiais e referências de página;
- normaliza unidades e mantém o texto original da evidência;
- calcula diferença absoluta e percentual entre medida de referência e configuração avaliada;
- gera um objeto estruturado para o agente editorial;
- cria o DOCX sem modificar o arquivo-modelo nem o PDF original;
- valida existência de seções, tabelas, fontes e campos pendentes.

### 2. Agente de IA — decisão editorial controlada

O agente não substitui a evidência. Ele deve apenas:

- escolher a ordem e a clareza da apresentação;
- resumir características já comprovadas;
- separar fato, configuração confirmada e pendência;
- sugerir onde uma informação deve aparecer no catálogo;
- recusar números, cores, materiais, normas ou componentes sem fonte;
- preservar o escopo comercial do catálogo, sem inserir instruções internas de produção.

### 3. DOCX estruturado — apresentação

- usa o modelo Word aprovado como base;
- preserva cabeçalho, margens, tipografia e hierarquia visual;
- usa títulos, tabelas e listas com estilos consistentes;
- inclui nota de evidência quando um dado não estiver comprovado;
- não publica o prompt, as regras do agente ou detalhes do pipeline.

## Portões de aprovação

1. **Fonte encontrada:** PDF e laudo aplicável identificados.
2. **Evidência suficiente:** cada dado publicado tem fonte ou está marcado como pendente.
3. **Medidas controladas:** diferenças são exibidas; tolerância de até 5% é apenas critério de comparação, não autorização automática.
4. **Modelo preservado:** o DOCX usa o template aprovado e não altera os arquivos de origem.
5. **Revisão editorial:** nenhuma instrução interna de fabricação é publicada no catálogo.
6. **Validação final:** DOCX abre, contém seções mínimas e está visualmente revisado.

## Saída do agente

O agente deve entregar duas camadas: (a) dados estruturados para auditoria; (b) texto editorial pronto para o DOCX. A camada de auditoria permanece fora do catálogo comercial e registra fonte, página, status e pendência.
