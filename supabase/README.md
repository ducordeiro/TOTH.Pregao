# Configuração do Supabase

1. Crie um projeto Supabase e habilite confirmação de e-mail em **Authentication**.
2. Execute `schema.sql` no SQL Editor e revise as políticas antes de produção.
3. Use somente a URL pública e a chave `anon` no cliente. Nunca coloque `service_role` no frontend.
4. Após o primeiro login, chame `seed_default_kanban_columns()` uma vez para o usuário autenticado.
5. A aplicação local permanece como fonte operacional offline. A sincronização deve ser implementada no backend e somente iniciada após clique e confirmação, com prévia de diferenças.
6. Antes do primeiro envio, exporte o SQLite, compare IDs/duplicidades e registre cada decisão em `sync_log`.

## Estado atual

O schema, Auth e RLS estão preparados, mas nenhuma credencial foi adicionada e nenhuma sincronização automática existe. Isso é intencional: evita envio de dados sem autorização. O Bloco 06 funciona localmente com SQLite.

## Migração segura

- Preserve `ocr_edital_web/data/pncp.sqlite3` e o backup datado em `backups/`.
- Faça a importação em transação, inicialmente para um projeto de homologação.
- Mapeie o usuário local para `auth.users.id`; não envie senhas nem tokens.
- Mostre contagens, conflitos e duplicidades antes do commit.
- Nunca atualize uma linha remota quando `updated_at` divergir sem decisão explícita.
- Registre enviados, importados, ignorados, conflitos e erros em `sync_log`.
