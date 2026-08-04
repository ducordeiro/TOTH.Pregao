# Manual de Git para o Projeto TOTH Pregão

Este manual foi feito para ajudar pessoas leigas e intermediárias a salvar alterações do projeto TOTH Pregão usando Git.

O objetivo é que você consiga:

- Entrar na pasta correta do projeto.
- Ver se existem alterações.
- Preparar arquivos para commit.
- Criar um commit com uma mensagem clara.
- Enviar o commit para o repositório remoto.
- Entender os erros mais comuns, incluindo problemas causados pelo OneDrive.

---

## 1. Onde está o projeto

O projeto está nesta pasta:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão
```

O app principal fica dentro desta subpasta:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão\ocr_edital_web
```

Para usar o Git, normalmente você deve estar na pasta raiz do projeto:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão
```

---

## 2. Abrindo o terminal no lugar certo

Abra o PowerShell e rode:

```powershell
cd "C:\Users\ducor\OneDrive\Documentos\Pregão"
```

Depois confirme se você está na pasta correta:

```powershell
pwd
```

O resultado deve mostrar:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão
```

---

## 3. Verificando o estado do Git

Antes de qualquer commit, rode:

```powershell
git status
```

Esse comando mostra se existem arquivos modificados, novos arquivos ou arquivos apagados.

### Quando não há alterações

Se aparecer algo parecido com:

```text
nothing to commit, working tree clean
```

significa que não existe nada novo para salvar em commit.

### Quando há alterações

Se aparecer algo como:

```text
Changes not staged for commit:
  modified:   ocr_edital_web/server.py
```

significa que existem arquivos alterados, mas eles ainda não foram preparados para o commit.

Se aparecer algo como:

```text
Untracked files:
  novo_arquivo.txt
```

significa que existe um arquivo novo que o Git ainda não está acompanhando.

---

## 4. Entendendo o fluxo básico

O fluxo normal do Git é:

```powershell
git status
git add .
git commit -m "Mensagem do commit"
git push
```

Em palavras simples:

- `git status` mostra o que mudou.
- `git add .` prepara as alterações.
- `git commit -m "..."` salva um ponto na história do projeto.
- `git push` envia esse ponto para o repositório remoto.

---

## 5. Preparando os arquivos para commit

Para preparar todas as alterações:

```powershell
git add .
```

Depois confira:

```powershell
git status
```

Se os arquivos aparecerem em uma seção parecida com:

```text
Changes to be committed:
```

eles já estão prontos para virar commit.

---

## 6. Criando o commit

Use:

```powershell
git commit -m "primeira versão TOTH Pregão"
```

Você pode trocar a mensagem por algo mais específico, por exemplo:

```powershell
git commit -m "Atualiza tela de propostas"
```

ou:

```powershell
git commit -m "Corrige geração de documentos do pregão"
```

### Como escrever boas mensagens

Boas mensagens de commit são curtas, claras e dizem o que mudou.

Exemplos bons:

```text
Adiciona tela de catálogo
Corrige cálculo do valor total
Atualiza layout da proposta
Cria integração com consulta PNCP
```

Exemplos ruins:

```text
alterações
teste
coisas
novo
```

---

## 7. Enviando para o GitHub ou repositório remoto

Depois do commit, rode:

```powershell
git push
```

Se tudo der certo, seu commit será enviado para o repositório remoto.

Depois confira:

```powershell
git status
```

O ideal é aparecer:

```text
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

Isso significa que:

- Sua máquina está atualizada.
- O repositório remoto também está atualizado.
- Não existem alterações pendentes.

---

## 8. Entendendo a mensagem "ahead of origin/main by 1 commit"

Você viu uma mensagem parecida com:

```text
Your branch is ahead of 'origin/main' by 1 commit.
```

Isso significa:

- O commit foi criado com sucesso na sua máquina.
- Esse commit ainda não foi enviado para o remoto.

Para resolver:

```powershell
git push
```

---

## 9. Problema comum: erro ao apagar `.git/objects`

Você viu uma mensagem parecida com:

```text
Deletion of directory '.git/objects/00' failed. Should I try again? (y/n)
```

Esse erro geralmente acontece porque o Windows ou o OneDrive segurou algum arquivo interno do Git.

Importante: `.git/objects` é uma pasta interna do Git. Ela não é uma pasta do app.

### O que fazer quando aparecer

Se aparecer uma vez:

```text
y
```

e aperte Enter.

Se continuar aparecendo várias vezes:

```text
n
```

e aperte Enter até voltar para o prompt do PowerShell.

Depois rode:

```powershell
git status
git log --oneline -1
```

Se o último commit aparecer no `git log`, então o commit foi criado.

---

## 10. Como confirmar que o commit existe

Rode:

```powershell
git log --oneline -1
```

Exemplo de resultado:

```text
abc1234 primeira versão TOTH Pregão
```

Isso mostra o commit mais recente.

Se a mensagem do seu commit aparecer, está tudo certo.

---

## 11. Como ver todos os arquivos alterados antes do commit

Use:

```powershell
git status
```

Para ver as diferenças dentro dos arquivos:

```powershell
git diff
```

Esse comando mostra o conteúdo que foi alterado.

Se você já usou `git add .`, use:

```powershell
git diff --staged
```

Esse comando mostra o que já está preparado para entrar no commit.

---

## 12. Como adicionar apenas um arquivo específico

Em vez de adicionar tudo com:

```powershell
git add .
```

você pode adicionar apenas um arquivo:

```powershell
git add "ocr_edital_web\server.py"
```

Isso é útil quando você quer separar commits por assunto.

Exemplo:

```powershell
git add "ocr_edital_web\frontend\src\App.tsx"
git commit -m "Atualiza tela principal"
```

---

## 13. Como desfazer um arquivo antes do commit

Se você alterou um arquivo sem querer e ainda não fez commit, primeiro veja o status:

```powershell
git status
```

Para descartar alterações de um arquivo específico:

```powershell
git restore "caminho\do\arquivo"
```

Exemplo:

```powershell
git restore "ocr_edital_web\frontend\src\App.tsx"
```

Atenção: esse comando apaga as alterações locais desse arquivo.

Use com cuidado.

---

## 14. Como tirar um arquivo da preparação do commit

Se você usou `git add .`, mas quer remover um arquivo da área de preparação:

```powershell
git restore --staged "caminho\do\arquivo"
```

Exemplo:

```powershell
git restore --staged "ocr_edital_web\server.py"
```

Isso não apaga a alteração. Apenas tira o arquivo do próximo commit.

---

## 15. Como ver o histórico de commits

Para ver os commits mais recentes:

```powershell
git log --oneline
```

Para ver somente os últimos 5:

```powershell
git log --oneline -5
```

Exemplo:

```text
abc1234 primeira versão TOTH Pregão
def5678 Atualiza frontend
ghi9012 Corrige servidor
```

---

## 16. Como saber em qual branch você está

Use:

```powershell
git branch
```

A branch atual aparece com um asterisco:

```text
* main
```

Também dá para ver pelo:

```powershell
git status
```

Exemplo:

```text
On branch main
```

---

## 17. Como baixar atualizações antes de trabalhar

Antes de começar a alterar o projeto em outro dia, é uma boa prática rodar:

```powershell
git pull
```

Isso baixa as alterações que estão no repositório remoto.

Fluxo recomendado ao começar o dia:

```powershell
cd "C:\Users\ducor\OneDrive\Documentos\Pregão"
git pull
git status
```

---

## 18. Fluxo recomendado completo

Use este fluxo sempre que terminar uma alteração importante:

```powershell
cd "C:\Users\ducor\OneDrive\Documentos\Pregão"
git status
git add .
git status
git commit -m "Descreva aqui o que foi alterado"
git push
git status
```

---

## 19. Exemplo prático completo

Imagine que você alterou o app e quer salvar a nova versão.

Entre na pasta:

```powershell
cd "C:\Users\ducor\OneDrive\Documentos\Pregão"
```

Veja o que mudou:

```powershell
git status
```

Prepare tudo:

```powershell
git add .
```

Confira:

```powershell
git status
```

Crie o commit:

```powershell
git commit -m "Atualiza app TOTH Pregão"
```

Envie:

```powershell
git push
```

Confira o resultado:

```powershell
git status
```

---

## 20. Como subir o app localmente

O app está configurado para rodar em:

```text
http://127.0.0.1:8765
```

Para iniciar, estando na pasta:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão
```

rode:

```powershell
.\iniciar_aplicacao_web.cmd
```

Ou abra o arquivo `iniciar_aplicacao_web.cmd` com duplo clique.

---

## 21. O que fazer antes de commitar

Antes de fazer commit, é bom verificar:

- O app abre corretamente.
- As telas principais funcionam.
- Nenhum arquivo temporário grande entrou sem querer.
- O `git status` mostra apenas arquivos que você realmente quer salvar.

Arquivos que geralmente não devem ser commitados:

- Logs temporários.
- Arquivos de cache.
- Arquivos gerados automaticamente sem necessidade.
- Pastas temporárias.

---

## 22. Dicas importantes sobre OneDrive

Seu projeto está dentro do OneDrive:

```powershell
C:\Users\ducor\OneDrive\Documentos\Pregão
```

Isso funciona, mas às vezes o OneDrive pode causar problemas com Git porque ele sincroniza arquivos ao mesmo tempo que o Git tenta modificar a pasta `.git`.

Problemas comuns:

- Erro ao apagar `.git/objects`.
- Arquivos internos travados.
- Lentidão ao fazer commit.
- Conflitos de sincronização.

Se isso acontecer muito, uma solução melhor é mover o projeto para uma pasta fora do OneDrive, por exemplo:

```powershell
C:\Projetos\Pregão
```

ou:

```powershell
C:\Users\ducor\Documents\Projetos\Pregão
```

Mas só faça isso com cuidado, depois de confirmar que tudo está salvo no repositório remoto.

---

## 23. Comandos mais usados

Ver estado:

```powershell
git status
```

Adicionar tudo:

```powershell
git add .
```

Criar commit:

```powershell
git commit -m "Mensagem"
```

Enviar:

```powershell
git push
```

Baixar atualizações:

```powershell
git pull
```

Ver histórico:

```powershell
git log --oneline
```

Ver último commit:

```powershell
git log --oneline -1
```

Ver branch:

```powershell
git branch
```

---

## 24. Checklist rápido para commit

Use esta lista sempre que for salvar uma versão:

```text
[ ] Estou na pasta C:\Users\ducor\OneDrive\Documentos\Pregão
[ ] Rodei git status
[ ] Revisei os arquivos alterados
[ ] Rodei git add .
[ ] Rodei git status de novo
[ ] Rodei git commit -m "mensagem clara"
[ ] Rodei git push
[ ] Rodei git status no final
```

---

## 25. Resumo final

O comando mais importante para se orientar é:

```powershell
git status
```

O fluxo mais comum é:

```powershell
git add .
git commit -m "Mensagem do commit"
git push
```

Se aparecer:

```text
nothing to commit, working tree clean
```

significa que está tudo limpo.

Se aparecer:

```text
Your branch is ahead of 'origin/main' by 1 commit.
```

significa que falta rodar:

```powershell
git push
```

Se aparecer erro em `.git/objects`, provavelmente é o OneDrive segurando arquivos internos do Git. Responda `n` se ele insistir muitas vezes, confirme o commit com `git log --oneline -1` e depois rode `git push`.

