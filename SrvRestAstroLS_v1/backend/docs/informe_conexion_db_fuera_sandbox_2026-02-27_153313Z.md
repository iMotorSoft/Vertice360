# Informe: conexión DB fuera de sandbox (2026-02-27 15:33:13Z)

## Resumen

- Diagnóstico ejecutado fuera de sandbox según protocolo operativo.
- Resultado: conectividad real a PostgreSQL `v360` correcta.
- Conclusión: si en sandbox aparecen `CAN_CONNECT=False`, `connection is bad` u `Operation not permitted`, se considera falso negativo del entorno restringido.

## Evidencia

1. Contenedor y puerto `5432`

```text
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'

NAMES                 IMAGE                      PORTS
imotorsoft-postgres   postgres:18.1-alpine3.22   0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
```

2. Test TCP `localhost:5432`

```text
TCP_5432_OK
```

3. Conexión con `psycopg.connect(...)`

```text
PSYCOPG_OK
CURRENT_DATABASE=v360
CURRENT_USER=administrator
```

4. Validación con `psql`

```text
PSQL_RC=0
v360|administrator
```

## Criterio aplicado

- TCP/`psycopg`/`psql` correctos fuera de sandbox.
- Diagnóstico final: DB disponible; cualquier falla desde sandbox es restricción de ejecución, no caída del servicio.
