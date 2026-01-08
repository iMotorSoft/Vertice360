#!/usr/bin/env python3
"""
Test sending a Template message via Meta WhatsApp Cloud API.
Templates (like 'hello_world') can be sent outside the 24h customer service window.

Requires env:
  META_VERTICE360_WABA_TOKEN
  META_VERTICE360_PHONE_NUMBER_ID
"""

import json
import os
import sys
import urllib.request
import urllib.error

# ---- Hardcode your test recipient ----
TO = "541130946950"
TEMPLATE_NAME = "hello_world"
LANGUAGE_CODE = "en_US"
# --------------------------------------

TOKEN = os.getenv("META_VERTICE360_WABA_TOKEN", "").strip()
PHONE_NUMBER_ID = os.getenv("META_VERTICE360_PHONE_NUMBER_ID", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v20.0").strip()

if not TOKEN or not PHONE_NUMBER_ID:
    print("ERROR: Missing env vars:")
    print("  META_VERTICE360_WABA_TOKEN")
    print("  META_VERTICE360_PHONE_NUMBER_ID")
    sys.exit(1)

url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"

payload = {
    "messaging_product": "whatsapp",
    "to": TO,
    "type": "template",
    "template": {
        "name": TEMPLATE_NAME,
        "language": {
            "code": LANGUAGE_CODE
        }
    },
}

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    url=url,
    data=data,
    method="POST",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    },
)

print("POST", url)
print("Payload:", payload)

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print("\nOK:", resp.status, resp.reason)
        print(body)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print("\nHTTP ERROR:", e.code, e.reason)
    print(body)
    sys.exit(2)
except Exception as e:
    print("\nERROR:", repr(e))
    sys.exit(3)
