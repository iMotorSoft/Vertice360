# Orquestador Admin Tools (DEV)

Herramientas administrativas de borrado para la demo del orquestador Vertice360.

## Advertencia

- Este endpoint es solo para `dev`.
- En `stg`/`prod` responde `403`.
- Requiere header `x-v360-admin-token` y token canónico `V360_ADMIN_TOKEN`.

## Configuración en DEV

```bash
export VERTICE360_ENV=dev
export V360_ADMIN_TOKEN="tu-token-seguro-dev"
```

Si `V360_ADMIN_TOKEN` está vacío en `dev`, el reset administrativo queda deshabilitado.

## Endpoint: reset por teléfono

- Método: `POST`
- URL: `/api/demo/vertice360-orquestador/admin/reset_phone`
- Body:

```json
{
  "phone": "+5491130946950"
}
```

### Ejemplo con curl

```bash
curl -X POST "http://localhost:7062/api/demo/vertice360-orquestador/admin/reset_phone" \
  -H "Content-Type: application/json" \
  -H "x-v360-admin-token: ${V360_ADMIN_TOKEN}" \
  -d '{"phone":"+5491130946950"}'
```

Respuesta esperada:

```json
{
  "ok": true,
  "phone": "+5491130946950",
  "deleted": {
    "events": 2,
    "visit_confirmations": 0,
    "visit_proposals": 0,
    "messages": 2,
    "tickets": 1,
    "conversations": 1,
    "leads": 1
  }
}
```

## Validación manual recomendada

1. `export V360_ADMIN_TOKEN=...`
2. Ejecutar `curl` al endpoint `admin/reset_phone`.
3. Enviar "Hola" al WhatsApp de dev y verificar que vuelva a disparar onboarding de primer contacto (Vera + link).
