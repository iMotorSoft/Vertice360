# Gupshup - Summary
Timestamp: 2026-02-06 11:15:33 -0300

- Added Gupshup env vars DEV/PRO + final selections and `gupshup_whatsapp_enabled()` in `backend/globalVar.py`.
- Scaffolded provider package under `backend/modules/messaging/providers/gupshup/whatsapp/` with public exports.
- Implemented `GupshupConfig`, async HTTP client, and service layer with SendAck and error wrapping.
- Implemented mapper with normalized inbound/status dataclasses, flexible parsing, and status normalization.
- Added registry helper in `backend/modules/messaging/providers/registry.py` for provider names.
- Added demo send endpoint and webhook for Gupshup in `backend/routes/messaging.py`, emitting SSE events (`messaging.outbound`, `messaging.inbound`, `messaging.status`).
- Added unit tests for Gupshup mapper in `backend/tests/test_gupshup_whatsapp_mapper.py`.
- Added Gupshup demo page and lab component in Astro/Svelte, with SSE filtering by provider.
- Added provider selector UI in Meta lab to route sends to Meta or Gupshup endpoints.
- Added Gupshup snippets and fixtures under `backend/modules/messaging/providers/gupshup/snippets/` and `backend/modules/messaging/providers/gupshup/fixtures/`.
