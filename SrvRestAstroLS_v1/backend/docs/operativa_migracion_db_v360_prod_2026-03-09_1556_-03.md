# Operativa de migracion DB v360 a produccion

Fecha/Hora de ejecucion (local): 2026-03-09 15:56:42 -0300  
Fecha/Hora de ejecucion (UTC): 2026-03-09 18:56:42Z

## Objetivo
Documentar el procedimiento para migrar la base `v360` desde entorno local/dev al servidor de produccion, con backup previo y rollback disponible.

## Alcance
- Base objetivo: `v360`
- Origen: PostgreSQL local (contenedor Docker `imotorsoft-postgres`)
- Destino: PostgreSQL remoto en `imotorsoft.com` (contenedor Docker `imotorsoft-postgres`)

## Pre-checks obligatorios
1. Confirmar contenedores activos en origen y destino.
2. Confirmar acceso SSH al servidor remoto.
3. Confirmar usuario/password de PostgreSQL con permisos de dump/restore.
4. Confirmar que se va a tocar solo `v360` (no otras bases).

## Variables recomendadas
```bash
export LOCAL_PG_HOST="127.0.0.1"
export LOCAL_PG_PORT="5432"
export LOCAL_PG_USER="administrator"
export LOCAL_PG_DB="v360"
export LOCAL_PG_CONTAINER="imotorsoft-postgres"

export REMOTE_HOST="imotorsoft.com"
export REMOTE_USER="administrator"
export REMOTE_PG_CONTAINER="imotorsoft-postgres"
export REMOTE_PG_DB="v360"

export TS_UTC="$(date -u +%Y%m%dT%H%M%SZ)"
export LOCAL_DUMP="/tmp/v360_local_source_${TS_UTC}.dump"
export REMOTE_BACKUP="/tmp/v360_remote_backup_${TS_UTC}.dump"
export REMOTE_SOURCE="/tmp/v360_local_source_${TS_UTC}.dump"
```

## Procedimiento

### 1) Validar bases existentes en origen y destino
```bash
PGPASSWORD='<PG_PASSWORD>' psql -h "$LOCAL_PG_HOST" -p "$LOCAL_PG_PORT" -U "$LOCAL_PG_USER" -d postgres -At \
  -c "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;"

ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "sudo docker exec ${REMOTE_PG_CONTAINER} sh -lc 'PGPASSWORD=\"<PG_PASSWORD>\" psql -h 127.0.0.1 -U ${LOCAL_PG_USER} -d postgres -At -c \"SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;\"'"
```

### 2) Generar dump del origen
Nota: usar `pg_dump` desde el contenedor cuando el cliente local no coincide en version con el server.
```bash
docker exec ${LOCAL_PG_CONTAINER} sh -lc \
  'PGPASSWORD="<PG_PASSWORD>" pg_dump -h 127.0.0.1 -U administrator -d v360 -Fc' \
  > "${LOCAL_DUMP}"
```

### 3) Generar backup previo en produccion (rollback)
```bash
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "sudo sh -lc 'docker exec ${REMOTE_PG_CONTAINER} sh -lc '\''PGPASSWORD=\"<PG_PASSWORD>\" pg_dump -h 127.0.0.1 -U administrator -d v360 -Fc'\'' > ${REMOTE_BACKUP}'"
```

### 4) Copiar dump origen al servidor remoto
```bash
scp "${LOCAL_DUMP}" ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_SOURCE}
```

### 5) Restaurar en produccion
```bash
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "sudo sh -lc 'docker exec -i ${REMOTE_PG_CONTAINER} sh -lc '\''PGPASSWORD=\"<PG_PASSWORD>\" pg_restore -h 127.0.0.1 -U administrator -d v360 --clean --if-exists --no-owner --no-privileges'\'' < ${REMOTE_SOURCE}'"
```

### 6) Validar post-restore
Comparar conteos clave entre origen y destino:
```bash
PGPASSWORD='<PG_PASSWORD>' psql -h "$LOCAL_PG_HOST" -p "$LOCAL_PG_PORT" -U "$LOCAL_PG_USER" -d v360 -At -F '|' -c "
SELECT 'projects', count(*) FROM projects
UNION ALL SELECT 'marketing_assets', count(*) FROM marketing_assets
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'developers', count(*) FROM developers
UNION ALL SELECT 'leads', count(*) FROM leads
UNION ALL SELECT 'conversations', count(*) FROM conversations
UNION ALL SELECT 'tickets', count(*) FROM tickets
UNION ALL SELECT 'messages', count(*) FROM messages
UNION ALL SELECT 'events', count(*) FROM events
UNION ALL SELECT 'visit_proposals', count(*) FROM visit_proposals
UNION ALL SELECT 'visit_confirmations', count(*) FROM visit_confirmations
UNION ALL SELECT 'demo_project_bundles', count(*) FROM demo_project_bundles
UNION ALL SELECT 'demo_project_facts', count(*) FROM demo_project_facts
UNION ALL SELECT 'demo_units', count(*) FROM demo_units
ORDER BY 1;"
```

En remoto:
```bash
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "sudo docker exec ${REMOTE_PG_CONTAINER} sh -lc 'PGPASSWORD=\"<PG_PASSWORD>\" psql -h 127.0.0.1 -U administrator -d v360 -At -F \"|\" -c \"SELECT '\''projects'\'', count(*) FROM projects UNION ALL SELECT '\''marketing_assets'\'', count(*) FROM marketing_assets UNION ALL SELECT '\''users'\'', count(*) FROM users UNION ALL SELECT '\''developers'\'', count(*) FROM developers UNION ALL SELECT '\''leads'\'', count(*) FROM leads UNION ALL SELECT '\''conversations'\'', count(*) FROM conversations UNION ALL SELECT '\''tickets'\'', count(*) FROM tickets UNION ALL SELECT '\''messages'\'', count(*) FROM messages UNION ALL SELECT '\''events'\'', count(*) FROM events UNION ALL SELECT '\''visit_proposals'\'', count(*) FROM visit_proposals UNION ALL SELECT '\''visit_confirmations'\'', count(*) FROM visit_confirmations UNION ALL SELECT '\''demo_project_bundles'\'', count(*) FROM demo_project_bundles UNION ALL SELECT '\''demo_project_facts'\'', count(*) FROM demo_project_facts UNION ALL SELECT '\''demo_units'\'', count(*) FROM demo_units ORDER BY 1;\"'"
```

## Rollback inmediato
Si la migracion falla funcionalmente, restaurar backup remoto previo:
```bash
ssh ${REMOTE_USER}@${REMOTE_HOST} \
  "sudo sh -lc 'docker exec -i ${REMOTE_PG_CONTAINER} sh -lc '\''PGPASSWORD=\"<PG_PASSWORD>\" pg_restore -h 127.0.0.1 -U administrator -d v360 --clean --if-exists --no-owner --no-privileges'\'' < ${REMOTE_BACKUP}'"
```

## Evidencia de ejecucion real (2026-03-09)
- Dump origen generado: `/tmp/v360_local_source_20260309T185104Z.dump` (44K)
- Backup previo remoto: `/tmp/v360_remote_backup_20260309T185104Z.dump` (33K)
- Restore remoto ejecutado sin errores (`exit code 0`)
- Conteos validados y coincidentes (local vs remoto):
  - conversations=2
  - demo_project_bundles=3
  - demo_project_facts=3
  - demo_units=10
  - developers=1
  - events=6
  - leads=2
  - marketing_assets=3
  - messages=4
  - projects=3
  - tickets=2
  - users=2
  - visit_confirmations=0
  - visit_proposals=0

## Limpieza opcional de artefactos
```bash
rm -f "${LOCAL_DUMP}"
ssh ${REMOTE_USER}@${REMOTE_HOST} "rm -f ${REMOTE_SOURCE}"
```
