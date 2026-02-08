from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx


def _load_global_var():
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from backend import globalVar

    return globalVar


def _check_get(client: httpx.Client, url: str) -> tuple[bool, int | None, str]:
    try:
        response = client.get(url, timeout=15.0)
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)
    if response.status_code == 502:
        return False, response.status_code, "502 from public URL (backend or tunnel not reachable)"
    if response.status_code >= 400:
        return False, response.status_code, response.text[:300]
    return True, response.status_code, "ok"


def _check_post_fixture(client: httpx.Client, url: str, payload: dict) -> tuple[bool, int | None, str]:
    try:
        response = client.post(url, json=payload, timeout=20.0)
    except Exception as exc:  # noqa: BLE001
        return False, None, str(exc)
    if response.status_code in (200, 201):
        return True, response.status_code, "ok"
    if response.status_code == 502:
        return False, response.status_code, "502 from public URL (backend or tunnel not reachable)"
    return False, response.status_code, response.text[:500]


def main() -> int:
    globalVar = _load_global_var()
    local_base = "http://localhost:7062"
    public_base = (globalVar.VERTICE360_PUBLIC_BASE_URL or "").strip()

    local_health = f"{local_base}/health"
    public_health = globalVar.public_url("/health")
    local_webhook = f"{local_base}/webhooks/messaging/gupshup/whatsapp"
    public_webhook = globalVar.public_url("/webhooks/messaging/gupshup/whatsapp")

    fixture_path = (
        Path(__file__).resolve().parents[1]
        / "modules"
        / "messaging"
        / "providers"
        / "gupshup"
        / "fixtures"
        / "inbound_minimal.json"
    )
    payload = {}
    if fixture_path.exists():
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

    print("Prerequisites:")
    print("1. Start backend: python backend/ls_iMotorSoft_Srv01_demo.py")
    print("2. Start cloudflared: cloudflared tunnel --url http://localhost:7062 --protocol http2 --edge-ip-version 4")
    print("3. Ensure public base URL is set in backend/globalVar.py")
    print("")
    print(f"PUBLIC_BASE_URL={public_base}")
    print(f"LOCAL_HEALTH_URL={local_health}")
    print(f"PUBLIC_HEALTH_URL={public_health}")
    print(f"LOCAL_GUPSHUP_WEBHOOK={local_webhook}")
    print(f"PUBLIC_GUPSHUP_WEBHOOK={public_webhook}")
    print("")

    if not public_base:
        print("FAIL: public base URL is empty.")
        return 1

    ok = True
    with httpx.Client() as client:
        local_health_ok, local_health_status, local_health_msg = _check_get(client, local_health)
        print(f"[CHECK] local health: ok={local_health_ok} status={local_health_status} msg={local_health_msg}")
        ok = ok and local_health_ok

        public_health_ok, public_health_status, public_health_msg = _check_get(client, public_health)
        print(f"[CHECK] public health: ok={public_health_ok} status={public_health_status} msg={public_health_msg}")
        ok = ok and public_health_ok

        local_webhook_ok, local_webhook_status, local_webhook_msg = _check_post_fixture(
            client, local_webhook, payload
        )
        print(
            "[CHECK] local gupshup webhook post:"
            f" ok={local_webhook_ok} status={local_webhook_status} msg={local_webhook_msg}"
        )
        ok = ok and local_webhook_ok

        public_webhook_ok, public_webhook_status, public_webhook_msg = _check_post_fixture(
            client, public_webhook, payload
        )
        print(
            "[CHECK] public gupshup webhook post:"
            f" ok={public_webhook_ok} status={public_webhook_status} msg={public_webhook_msg}"
        )
        ok = ok and public_webhook_ok

    print("")
    print("Webhook URLs to paste in provider consoles:")
    print(f"META_WEBHOOK_URL={globalVar.public_url('/webhooks/messaging/meta/whatsapp')}")
    print(f"GUPSHUP_WEBHOOK_URL={globalVar.public_url('/webhooks/messaging/gupshup/whatsapp')}")

    if ok:
        print("\nRESULT=PASS")
        return 0
    print("\nRESULT=FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
