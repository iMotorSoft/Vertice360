# Gupshup - Production Status
Timestamp: 2026-02-08 20:54:43 -0300

## Summary
- Production webhook URL configured in Gupshup as:
  - `https://demo.pozo360.imotorsoft.com/webhooks/messaging/gupshup/whatsapp`
- Public base URL now points to production domain in `backend/globalVar.py`.
- Basic production smoke tests passed.

## Validation Executed
- `POST /webhooks/messaging/gupshup/whatsapp` with inbound fixture:
  - HTTP `201 Created`
  - Body: `{"ok":true}`
- `POST /webhooks/messaging/gupshup/whatsapp` with status fixture:
  - HTTP `201 Created`
  - Body: `{"ok":true}`
- `POST /api/demo/messaging/gupshup/whatsapp/send`:
  - HTTP `200 OK`
  - Response included `ok: true`, `provider: gupshup`, `status: submitted`
  - `message_id`: `82cc9ab7-0edc-40b5-970c-cf43367a7ba3`

## Observation
- `GET /health` on `demo.pozo360.imotorsoft.com` returns frontend HTML (nginx routing), not backend health JSON.
  - This does not block webhook delivery.
  - Recommend routing `/health` to backend for monitoring.

## Critical Caution
- Keep provider consistency across all endpoints during validation and operations.
- Inbound webhook, outbound send endpoint, and status/reply flow must belong to the same provider (`gupshup` or `meta`).
- Mixing providers (for example, sending with Gupshup but checking Meta webhook/reply paths) can produce false failures and delayed debugging.
- This session required extra troubleshooting because some checks still pointed to Meta endpoints while validating Gupshup webhook notifications.
