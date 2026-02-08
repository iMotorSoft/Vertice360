
import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.modules.messaging.providers.gupshup.whatsapp.mapper import parse_inbound

# Captured from logs
raw_json = """
{
  "app": "vertice360dev",
  "timestamp": 1770566667877,
  "version": 2,
  "type": "message",
  "payload": {
    "id": "wamid.HBgNNTQ5MTEzMDk0Njk1MBUCABIYIEE1OTlBOUIyRDVCNUEzQkY5MkRCMEEyMzYyRUYxRkE1AA==",
    "source": "5491130946950",
    "type": "text",
    "payload": {
      "text": "Hi"
    },
    "sender": {
      "phone": "5491130946950",
      "name": "Mario Rojas",
      "country_code": "54",
      "dial_code": "91130946950"
    }
  }
}
"""

def main():
    data = json.loads(raw_json)
    print(f"Input payload keys: {list(data.keys())}")
    
    messages = parse_inbound(data)
    print(f"Parsed {len(messages)} messages.")
    
    if len(messages) == 0:
        print("FAIL: Parser found 0 messages.")
        sys.exit(1)
        
    msg = messages[0]
    print(f"SUCCESS: Parsed message from {msg.from_} saying '{msg.text}'")

if __name__ == "__main__":
    main()
