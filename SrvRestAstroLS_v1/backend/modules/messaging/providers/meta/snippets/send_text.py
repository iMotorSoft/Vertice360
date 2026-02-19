#!/usr/bin/env python3
"""
Quick & dirty Meta WhatsApp Cloud API sender (hardcoded).

Requires env managed via globalVar:
  META_VERTICE360_WABA_TOKEN
  META_VERTICE360_PHONE_NUMBER_ID

Optional:
  META_GRAPH_VERSION (default v20.0)
"""

import json
import sys
import urllib.request
import urllib.error

import globalVar

# ---- Hardcode your test recipient + message here ----
TO = "541130946950"  # <-- your WhatsApp recipient (allowed in test env)
TEXT = "BSD Hola! Prueba WhatsApp Cloud API (Meta) desde iMotorSoft Messaging Hub."
# NOTE: This message will likely NOT be delivered if the user hasn't messaged the business
# in the last 24 hours (use a Template instead).
# ----------------------------------------------------

TOKEN = (globalVar.META_VERTICE360_WABA_TOKEN or "").strip()
PHONE_NUMBER_ID = (globalVar.META_VERTICE360_PHONE_NUMBER_ID or "").strip()
GRAPH_VERSION = (globalVar.META_GRAPH_VERSION or "v20.0").strip()

if not TOKEN or not PHONE_NUMBER_ID:
    print("ERROR: Missing env vars:")
    print("  META_VERTICE360_WABA_TOKEN")
    print("  META_VERTICE360_PHONE_NUMBER_ID")
    sys.exit(1)

url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"

payload = {
    "messaging_product": "whatsapp",
    "to": TO,
    "type": "text",
    "text": {"body": TEXT},
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
