from __future__ import annotations

import os
import uuid

import httpx
import globalVar

async def send_message(to: str, text: str) -> dict:
    """
    Sends a WhatsApp text message using the Meta Cloud API.
    """
    if os.environ.get("DEMO_DISABLE_META_SEND") == "1":
        message_id = f"demo-{uuid.uuid4().hex}"
        return {"status": "skipped", "messages": [{"id": message_id}]}
    if not globalVar.meta_whatsapp_enabled():
        return {"error": "Meta WhatsApp not configured (missing env vars)"}

    url = f"https://graph.facebook.com/{globalVar.META_GRAPH_VERSION}/{globalVar.META_VERTICE360_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {globalVar.META_VERTICE360_WABA_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers, timeout=20.0)
        
        # Raise for status to handle HTTP errors, or handle manually if preferred.
        # Here we return the JSON response or the error detail.
        if response.is_error:
             # Basic error handling
            return {
                "status": "error",
                "status_code": response.status_code,
                "response": response.text
            }
            
        return response.json()
