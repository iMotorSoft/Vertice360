# Informe: conexión DB fuera de sandbox

- Fecha/hora (UTC): 2026-02-24 21:51:55Z
- Entorno: `backend` (validación operativa)
- Objetivo: evitar falsos negativos de conectividad a `v360` cuando el sandbox bloquea red local.

## Contexto

Durante la validación inicial, la app devolvió `CAN_CONNECT=False` y `connection is bad`, pero el contenedor PostgreSQL estaba activo y exponiendo `0.0.0.0:5432->5432`.

## Causa raíz

El fallo no era de PostgreSQL ni credenciales: era restricción del sandbox de ejecución para conexiones locales (`localhost` / socket/docker), que bloquea pruebas reales de red.

## Validación correcta (fuera de sandbox)

Se ejecutaron pruebas con permisos escalados y los resultados fueron exitosos:

1. Test TCP:
   - `TCP_OK localhost ('127.0.0.1', 5432)`
   - `TCP_OK 127.0.0.1 ('127.0.0.1', 5432)`
   - `TCP_OK ::1 ('::1', 5432, 0, 0)`
2. Test `psycopg`:
   - `PSYCOPG_OK ('v360', 'administrator')`
3. Test `psql`:
   - `current_database = v360`
   - `current_user = administrator`

## Regla operativa para próximos diagnósticos

Si aparece error de conexión desde el agente (`CAN_CONNECT=False`, `connection is bad`, `Operation not permitted`), validar primero si la ejecución está limitada por sandbox.  
Para confirmar conectividad real de DB local, repetir el chequeo fuera de sandbox antes de concluir que la base está caída.

## Checklist rápido

1. Confirmar `docker ps` y mapeo de puerto `5432`.
2. Ejecutar test TCP a `localhost:5432` fuera de sandbox.
3. Ejecutar `psycopg.connect(...)` fuera de sandbox.
4. Ejecutar `psql` con usuario/DB objetivo.
5. Registrar resultado con fecha/hora en `docs/`.
