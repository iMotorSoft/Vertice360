# Gupshup Webhook E2E (Dev Tunnel)

## Prerequisites (required)
1. Start backend:
   - `python backend/ls_iMotorSoft_Srv01_demo.py`
2. Start cloudflared tunnel:
   - `cloudflared tunnel --url http://localhost:7062 --protocol http2 --edge-ip-version 4`
3. Confirm public URLs:
   - `python backend/scripts/print_public_webhook_urls.py`

## Verify end-to-end reachability
Run:

`python backend/scripts/verify_gupshup_webhook_e2e.py`

This script checks:
- local backend health (`http://localhost:7062/health`)
- public health through Cloudflare tunnel (`/health`)
- local webhook POST (`/webhooks/messaging/gupshup/whatsapp`)
- public webhook POST through tunnel (`/webhooks/messaging/gupshup/whatsapp`)

If backend or tunnel is down, you will see explicit FAIL lines (often `502` from public URL).
