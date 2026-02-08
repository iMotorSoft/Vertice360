import os
import sys
import httpx
from pathlib import Path

# Add backend root to path to import globalVar if needed
project_root = Path(__file__).resolve().parents[4]
sys.path.append(str(project_root))

try:
    from backend import globalVar
    host = globalVar.HOST
    port = globalVar.PORT
except ImportError:
    host = "localhost"
    port = 7062

base_url = os.getenv("VERTICE360_API_BASE") or f"http://{host}:{port}"
url = f"{base_url.rstrip('/')}/api/demo/messaging/gupshup/whatsapp/send"

to = os.getenv("GUPSHUP_TEST_TO")
text = os.getenv("GUPSHUP_TEST_TEXT", "Hello from Gupshup demo snippet")

if not to:
    print("Error: set GUPSHUP_TEST_TO with a destination number.")
    sys.exit(1)

payload = {"to": to, "text": text}

print("--- Gupshup Demo Send ---")
print(f"URL: {url}")
print(f"To: {to}")

try:
    response = httpx.post(url, json=payload, timeout=15.0)
    print(f"Status: {response.status_code}")
    try:
        print("Response:")
        print(response.json())
    except Exception:
        print(response.text)
except httpx.RequestError as exc:
    print(f"Request error: {exc}")
