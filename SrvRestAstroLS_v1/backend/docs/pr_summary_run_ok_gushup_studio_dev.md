# PR Summary - run ok gushup studio dev

## Scope
Fixes and validation for WhatsApp Gupshup flow in development, covering webhook parsing, provider routing from AI Workflow Studio, and unified send endpoint stability.

## Main Changes
- Hardened Gupshup webhook parser for live payload variants (`message-event`, nested payloads, sender object handling).
- Added provider alias normalization (`gupshup_whatsapp`, `gs`, `meta_whatsapp`) to avoid wrong provider fallback.
- Updated Studio API to normalize provider before POSTing unified send requests.
- Updated Studio RunInspector to auto-detect provider from ticket events and preserve manual override.
- Refactored unified backend endpoint to use an internal async helper for Gupshup path, removing a runtime 500 caused by internal call to a decorated handler.

## Files Updated
- `backend/modules/messaging/providers/gupshup/whatsapp/mapper.py`
- `backend/modules/messaging/providers/registry.py`
- `backend/routes/messaging.py`
- `astro/src/lib/vertice360_ai_workflow_studio/api.js`
- `astro/src/lib/vertice360_ai_workflow_studio/ui/RunInspector.svelte`
- `backend/tests/test_gupshup_whatsapp_mapper.py`
- `backend/tests/test_demo_whatsapp_unified_send.py`

## Validation Executed
- `uv run pytest -q tests/test_gupshup_whatsapp_mapper.py -q` -> PASS
- `uv run pytest -q tests/test_demo_whatsapp_unified_send.py -q` -> PASS
- `uv run pytest -q tests/test_gupshup_demo_error_shape.py -q` -> PASS
- `python scripts/verify_gupshup_webhook_e2e.py` -> PASS
- Manual curl against unified endpoint:
  - `POST /api/demo/messaging/whatsapp/send` with `provider=gupshup_whatsapp`
  - Result: `200 OK`, `provider=gupshup`, message submitted.

## Operational Notes
- `billing-event` webhook is not inbound chat content; it should not be interpreted as user message.
- Always restart backend after routing/parser changes.
- Keep tunnel URL and provider console callback URL aligned.
