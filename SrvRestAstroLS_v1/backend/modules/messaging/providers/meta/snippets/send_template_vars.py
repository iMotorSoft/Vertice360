#!/usr/bin/env python3
"""
Example of sending a Template message WITH VARIABLES (parameters).

To send "free text" (variable content) within a template, the template 
must be created in Meta with placeholders like {{1}}, {{2}}, etc.

Example Template "order_update":
"Hello {{1}}, your order {{2}} is now {{3}}."

This script demonstrates the structure to fill those placeholders.
"""

import json
import os
import sys
import urllib.request
import urllib.error

# ---- CONFIGURATION ----
TO = "541130946950"
# WARNING: You must have a template named exactly this in your Meta Manager
# with at least 1 parameter {{1}} for this specific example to work.
# 'hello_world' usually does NOT accept parameters and will fail if you send them.
TEMPLATE_NAME = "sample_issue_resolution" # Example standard template often available
LANGUAGE_CODE = "en_US"

# Defines the values for {{1}}, {{2}}, etc.
# Text is "free" here, but restricted to the position of the placeholder.
PARAMETERS = [
    {"type": "text", "text": "Juan Perez"},  # {{1}}
    # {"type": "text", "text": "12345"},    # {{2}} - uncomment if template has 2 vars
]
# -----------------------

TOKEN = os.getenv("META_VERTICE360_WABA_TOKEN", "").strip()
PHONE_NUMBER_ID = os.getenv("META_VERTICE360_PHONE_NUMBER_ID", "").strip()
GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v20.0").strip()

if not TOKEN or not PHONE_NUMBER_ID:
    print("ERROR: Missing env vars")
    sys.exit(1)

url = f"https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages"

payload = {
    "messaging_product": "whatsapp",
    "to": TO,
    "type": "template",
    "template": {
        "name": TEMPLATE_NAME,
        "language": {"code": LANGUAGE_CODE},
        "components": [
            {
                "type": "body",
                "parameters": PARAMETERS
            }
        ]
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
print(f"Sending Template: {TEMPLATE_NAME} with params: {[p['text'] for p in PARAMETERS]}")

try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print("\nOK:", resp.status, resp.reason)
        print(body)
except urllib.error.HTTPError as e:
    body = e.read().decode("utf-8", errors="replace")
    print("\nHTTP ERROR:", e.code, e.reason)
    print(body)
    print("\nNOTE: This error likely means the template name doesn't confirm to the parameters provided.")
    sys.exit(2)
except Exception as e:
    print("\nERROR:", repr(e))
    sys.exit(3)
