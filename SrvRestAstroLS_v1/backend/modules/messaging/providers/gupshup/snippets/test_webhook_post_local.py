import os
import sys
import json
import httpx
from pathlib import Path

# Add backend root to path to import globalVar if needed
project_root = Path(__file__).resolve().parents[4]
sys.path.append(str(project_root))

try:
    from backend import globalVar
    port = globalVar.PORT
except ImportError:
    port = 7062

base_url = os.getenv("VERTICE360_API_BASE") or f"http://localhost:{port}"
url = f"{base_url.rstrip('/')}/webhooks/messaging/gupshup/whatsapp"

fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures"
fixture_name = os.getenv("GUPSHUP_WEBHOOK_FIXTURE", "inbound_minimal.json")
fixture_path = fixtures_dir / fixture_name

if not fixture_path.exists():
    print(f"Fixture not found: {fixture_path}")
    sys.exit(1)

payload = json.loads(fixture_path.read_text())

print("--- Gupshup Webhook Test ---")
print(f"URL: {url}")
print(f"Fixture: {fixture_path.name}")

headers = {
    "User-Agent": "Gupshup-Webhook-Tester/1.0",
    "Content-Type": "application/json",
}

try:
    response = httpx.post(url, json=payload, headers=headers, timeout=10.0)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code in (200, 201):
        print("SUCCESS: Webhook accepted.")
    else:
        print("FAILURE: Webhook not accepted.")
except httpx.RequestError as exc:
    print(f"Request error: {exc}")
