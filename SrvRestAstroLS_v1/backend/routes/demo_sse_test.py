import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from litestar import Controller, get
from litestar.response import Stream
from litestar.status_codes import HTTP_200_OK


class SseTestController(Controller):
    path = "/api/demo/sse-test"

    @get("/stream", status_code=HTTP_200_OK)
    async def sse_stream(self) -> Stream:
        """
        Calculated endpoint URL: /api/demo/sse-test/stream
        """
        async def generator() -> AsyncGenerator[str, None]:
            # 1. Handshake immediately
            yield ": connected\n\n"
            
            seq = 0
            while True:
                seq += 1
                data = {
                    "message": "tick",
                    "timestamp": datetime.now().isoformat(),
                    "seq": seq
                }
                # SSE format: data: <payload>\n\n
                yield f"data: {json.dumps(data)}\n\n"
                await asyncio.sleep(2)

        return Stream(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
