# Status Workflow Handoff Fix

- Fecha local: 2026-02-10 22:46:22 -03
- Fecha UTC: 2026-02-11_01-46-22Z
- Repo: backend

## Estado
- Implementado fix para evitar reinicio de onboarding por saludos cortos durante scheduling.
- Reset de sesión limitado a comandos explícitos: `reiniciar`, `empezar de nuevo`, `empezar nuevamente`, `reset`, `cancelar`.
- Persistencia de estado por clave estable: `provider + app + phone`.
- Agregado stage handling con transición a `handoff_scheduling` y re-pregunta de `día y franja horaria` para inputs ambiguos.
- Logs INFO de transición de stage añadidos.

## Validación
- `python -m compileall -q backend` -> OK
- `pytest -q` -> 72 passed

