# Ajustes e continuidade da auditoria

A consulta textual agora relaciona o indice FTS a opportunities pelo rowid mantido pelas migracoes e pelo repositorio. Evita carregar o documento textual do indice apenas para obter o identificador. Nao altera termos, filtros ou regras de classificacao.

Seis comparacoes na mesma transacao retornaram resultados identicos: busca mensal, UF, frase, segunda pagina, pontuacao e pagina vazia. Tempos completos do repositorio estao em search-optimization-2026-09-12.json. Por exemplo, UF passou de 398 para 98 ms; frase de 2.274 para 482 ms; segunda pagina de 393 para 144 ms. A ordem dos ensaios favorece cache de disco nas chamadas posteriores, portanto os numeros nao constituem garantia universal de latencia.

Foi reproduzida e corrigida uma falha SQL ao consultar pagina alem do fim com palavra-chave e pontuacao. A contagem agora inclui a mesma fonte FTS da consulta principal e retorna total correto com pagina vazia.

Validacao: a suite de 236 testes teve 235 aprovados e uma falha no novo teste de atualizacao de itens. O teste usava escrita SQL direta, que nao e o fluxo de indexacao do app. Ele foi ajustado para usar replace_opportunity_items; os dois novos testes passaram em seguida. A verificacao integral de correspondencia rowid/identidade do FTS retornou zero divergencias. O quick_check integral atingiu o limite de 600 segundos, portanto a integridade fisica integral ainda nao foi certificada. Nao houve reconstrucoes ou exclusoes no banco.

Na verificacao de continuidade, o antigo extrator PID 25000 nao existia mais. O status running estava desatualizado desde 12/09/2026 19:50. Os logs terminaram sem traceback, portanto nao permitem determinar a causa do encerramento. A coleta foi retomada com o mesmo escopo e limites; PID 13256, run c11ad7ba3ce243faa07350d0015b0e28. Novas chamadas e gravacoes foram confirmadas. O percentual deste run mede uma nova fila de pendencias e nao e diretamente comparavel ao percentual do run anterior.

O servidor foi restaurado na porta 8765 (PID 21672) para carregar os ajustes. A coleta continua em processo separado. Sem commit ou push nesta rodada.
