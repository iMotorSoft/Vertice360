# Operativa: limpieza DB para pruebas (v360)

Fecha/hora UTC: 2026-03-02 15:30:19Z  
Fecha/hora local: 2026-03-02 12:30:19 -03

## Objetivo

Dejar la base `v360` limpia para pruebas, preservando catálogos base de demo.

## Alcance de limpieza

Se vacían solo tablas transaccionales:

- `leads`
- `conversations`
- `tickets`
- `messages`
- `events`
- `visit_proposals`
- `visit_confirmations`

Se conservan catálogos:

- `projects`
- `marketing_assets`
- `users`
- `developers`

## Prerrequisitos

- Variable `DB_PG_V360_URL` configurada y apuntando a DB `v360`.
- `psql` disponible.

## Comando de limpieza

```bash
psql "${DB_PG_V360_URL/postgresql+psycopg/postgresql}" -v ON_ERROR_STOP=1 \
  -c "begin; \
      truncate table visit_confirmations, visit_proposals, events, messages, tickets, conversations, leads restart identity; \
      commit;"
```

## Verificación rápida

```bash
psql "${DB_PG_V360_URL/postgresql+psycopg/postgresql}" -v ON_ERROR_STOP=1 -c "\
select 'leads' as table, count(*) from leads union all\
select 'conversations', count(*) from conversations union all\
select 'tickets', count(*) from tickets union all\
select 'messages', count(*) from messages union all\
select 'events', count(*) from events union all\
select 'visit_proposals', count(*) from visit_proposals union all\
select 'visit_confirmations', count(*) from visit_confirmations union all\
select 'projects', count(*) from projects union all\
select 'marketing_assets', count(*) from marketing_assets union all\
select 'users', count(*) from users union all\
select 'developers', count(*) from developers;"
```

Resultado esperado:

- Transaccionales en `0`.
- Catálogos con sus seeds (`projects=3`, `marketing_assets=3`, `users=2`, `developers=1`, salvo que se hayan modificado manualmente).
