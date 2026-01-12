from __future__ import annotations

import asyncio
import time

from backend.modules.vertice360_workflow_demo.services import process_inbound_message


async def main() -> None:
    now_ms = int(time.time() * 1000)
    first_inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491100000001",
        "to": "PHONE_ID",
        "messageId": "wamid-demo-001",
        "text": "Hola, quiero info",
        "timestamp": now_ms,
        "mediaCount": 0,
    }
    first_result = await process_inbound_message(first_inbound)
    print(first_result)

    second_inbound = {
        "provider": "meta_whatsapp",
        "channel": "whatsapp",
        "from": "+5491100000001",
        "to": "PHONE_ID",
        "messageId": "wamid-demo-002",
        "text": "Adjunto mi DNI y comprobante",
        "timestamp": now_ms + 1000,
        "mediaCount": 2,
        "ticketId": first_result.get("ticketId"),
    }
    second_result = await process_inbound_message(second_inbound)
    print(second_result)


if __name__ == "__main__":
    asyncio.run(main())
