# Operativa: diagnóstico de conectividad DB (v360)

## Objetivo

Evitar falsos negativos de conectividad a PostgreSQL (`v360`) cuando la ejecución del agente está limitada por sandbox.

## Señales típicas de falso negativo

- `CAN_CONNECT=False`
- `connection is bad`
- `Operation not permitted`

Si aparecen estos errores desde un entorno restringido, no concluir caída de DB sin validar fuera de sandbox.

## Protocolo de validación

1. Confirmar contenedor y mapeo de puerto `5432` con `docker ps`.
2. Ejecutar test TCP a `localhost:5432` fuera de sandbox.
3. Ejecutar conexión con `psycopg.connect(...)` fuera de sandbox.
4. Ejecutar `psql` con usuario/DB objetivo y validar:
   - `current_database`
   - `current_user`
5. Registrar resultado con fecha/hora UTC en `docs/`.

## Criterio de diagnóstico

- Si fuera de sandbox los tests TCP/`psycopg`/`psql` son correctos, el problema es restricción de ejecución del entorno, no disponibilidad real de PostgreSQL.

## Caso de referencia

- [Informe: conexión DB fuera de sandbox (2026-02-24 21:51:55Z)](./informe_conexion_db_fuera_sandbox_2026-02-24_215155Z.md)
