from __future__ import annotations

import argparse
import asyncio
import json
import sys
import threading
from queue import Queue
from pathlib import Path


def _load_workflow_services():
    root_dir = Path(__file__).resolve().parents[2]
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from backend.modules.vertice360_workflow_demo import services

    return services


async def _run(to: str, text: str) -> dict:
    services = _load_workflow_services()
    return await services._send_whatsapp_text_with_context(
        "gupshup_whatsapp",
        to,
        text,
        ticket_id="SMOKE-GUPSHUP",
        run_id="manual-smoke",
    )


def _worker(to: str, text: str, queue: Queue) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_run(to, text))
    except Exception as exc:  # noqa: BLE001
        queue.put(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "upstream_status": getattr(exc, "upstream_status", None),
                "upstream_body": getattr(exc, "upstream_body", None),
            }
        )
        return
    finally:
        try:
            loop.stop()
        except Exception:  # noqa: BLE001
            pass
        loop.close()
    queue.put({"ok": True, "result": result})


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test workflow outbound via Gupshup")
    parser.add_argument("--to", default="5491130946950")
    parser.add_argument("--text", default="Smoke test workflow reply via Gupshup ✅")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    queue: Queue = Queue(maxsize=1)
    worker = threading.Thread(target=_worker, args=(args.to, args.text, queue), daemon=True)
    worker.start()
    worker.join(timeout=args.timeout_seconds)

    if worker.is_alive():
        print("SMOKE_RESULT=FAIL")
        print(f"error=timeout after {args.timeout_seconds}s")
        return 1

    if queue.qsize() == 0:
        print("SMOKE_RESULT=FAIL")
        print("error=no_result_from_worker")
        return 1

    outcome = queue.get()
    if not outcome.get("ok"):
        print("SMOKE_RESULT=FAIL")
        print(f"error_type={outcome.get('error_type')}")
        print(f"error={outcome.get('error')}")
        if outcome.get("upstream_status") is not None:
            print(f"upstream_status={outcome.get('upstream_status')}")
        if outcome.get("upstream_body"):
            print(f"upstream_body={outcome.get('upstream_body')}")
        return 1

    result = outcome.get("result") or {}
    message_id = result.get("id") or result.get("message_id") or result.get("raw", {}).get("id")
    print("SMOKE_RESULT=PASS")
    print(f"message_id={message_id}")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
