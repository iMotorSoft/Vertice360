# Inbound Router Mode (Gupshup WhatsApp)

- El router inbound canónico del webhook `POST /webhooks/messaging/gupshup/whatsapp` es `orquestador` por defecto.
- Variable canónica: `V360_INBOUND_ROUTER_MODE` con valores válidos `orquestador|workflow`.
- Si el valor es inválido o está ausente, el fallback seguro es `orquestador`.
- El workflow demo (`vertice360_workflow_demo`) sigue disponible para pruebas internas por sus endpoints demo existentes.
- Para enrutar inbound del webhook hacia workflow en pruebas, setear:

```bash
export V360_INBOUND_ROUTER_MODE=workflow
```
