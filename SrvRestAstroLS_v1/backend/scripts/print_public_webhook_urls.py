from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    try:
        from backend import globalVar
    except Exception:
        print("META_WEBHOOK_URL=")
        print("GUPSHUP_WEBHOOK_URL=")
        return 0

    print(f"META_WEBHOOK_URL={globalVar.public_url('/webhooks/messaging/meta/whatsapp')}")
    print(f"GUPSHUP_WEBHOOK_URL={globalVar.public_url('/webhooks/messaging/gupshup/whatsapp')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
