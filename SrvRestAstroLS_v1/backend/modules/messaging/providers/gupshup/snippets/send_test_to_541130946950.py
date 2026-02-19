"""Local test helper. Requires backend running and GUPSHUP_* env vars set."""

import sys
import json
import httpx

import globalVar


def main() -> int:
    default_base = f"http://{globalVar.HOST}:{globalVar.PORT}"
    base_url = globalVar.get_env_str("VERTICE360_BACKEND_URL", default_base).rstrip("/")
    url = f"{base_url}/api/demo/messaging/gupshup/whatsapp/send"

    payload = {
        "to": "541130946950",
        "text": "Prueba Gupshup Vertice360 (Debug) #1",
    }

    print("--- Gupshup Demo Send (Debug) ---")
    print(f"URL: {url}")

    try:
        response = httpx.post(url, json=payload, timeout=15.0)
    except httpx.RequestError as exc:
        print("ERROR: Backend not reachable.")
        print(f"Details: {exc}")
        return 1

    print(f"Status: {response.status_code}")

    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            data = response.json()
            print(json.dumps(data, indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(response.text)
    else:
        print(response.text)

    if response.status_code >= 400:
        print("ERROR: Non-2xx response from backend.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
