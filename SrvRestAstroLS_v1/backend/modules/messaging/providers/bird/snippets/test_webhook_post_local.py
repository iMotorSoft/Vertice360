import sys
import os
import json
import httpx
from pathlib import Path

# Add backend root to path to import globalVar if needed
project_root = Path(__file__).resolve().parents[4] 
sys.path.append(str(project_root))

try:
    from backend import globalVar
    PORT = globalVar.PORT
except ImportError:
    print("Could not import globalVar, defaulting to 7062")
    PORT = 7062

URL = f"http://localhost:{PORT}/webhooks/bird"

def test_webhook():
    print(f"Target URL: {URL}")
    
    payload = {
        "id": "evt_123456_httpx",
        "from": "123456789",
        "to": "987654321",
        "createdDatetime": "2023-10-27T10:00:00Z",
        "content": {
            "text": "Hello Vertice360 from Local Script (httpx)!"
        },
        "meta": "demo-data"
    }
    
    headers = {
        "User-Agent": "Bird-Webhook-Tester/1.0",
        "X-Bird-Signature": "fake-sig-for-now",
        "Content-Type": "application/json"
    }

    try:
        response = httpx.post(URL, json=payload, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in (200, 201):
            print("SUCCESS: Webhook accepted.")
        else:
            print("FAILURE: Webhook not accepted.")
            
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}.")
    except Exception as exc:
        print(f"An unexpected error occurred: {exc}")

if __name__ == "__main__":
    test_webhook()
