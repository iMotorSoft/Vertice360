import sys
import httpx
from pathlib import Path

# Add backend root to path to import globalVar if needed
project_root = Path(__file__).resolve().parents[4]
sys.path.append(str(project_root))

try:
    from backend import globalVar
except ImportError:
    import globalVar  # type: ignore

host = globalVar.HOST
port = globalVar.PORT

base_url = globalVar.get_env_str("VERTICE360_API_BASE", f"http://{host}:{port}")
url = f"{base_url.rstrip('/')}/api/demo/messaging/gupshup/whatsapp/send"

to = globalVar.get_env_str("GUPSHUP_TEST_TO")
text = globalVar.get_env_str("GUPSHUP_TEST_TEXT", "Hello from Gupshup demo snippet")

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
