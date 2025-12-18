
import os
import httpx
import sys
import json

# --- CONFIGURATION (Load from ENV) ---
BIRD_API_KEY = os.getenv("BIRD_API_KEY_VERTICE360_DEV_DEBUG") or os.getenv("BIRD_API_KEY_VERTICE360_DEV")
BIRD_WORKSPACE_ID = os.getenv("BIRD_WORKSPACE_ID")
BIRD_API_BASE = os.getenv("BIRD_API_BASE", "https://api.bird.com")

if not BIRD_API_KEY:
    print("Error: BIRD_API_KEY environment variable is not set.")
    sys.exit(1)

if not BIRD_WORKSPACE_ID:
    print("Error: BIRD_WORKSPACE_ID environment variable is not set.")
    print("Please find it in your Bird Dashboard URL and run: export BIRD_WORKSPACE_ID=...")
    sys.exit(1)

HEADERS = {
    "Authorization": f"AccessKey {BIRD_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "X-Bird-Workspace-ID": BIRD_WORKSPACE_ID
}

def get_whatsapp_channel():
    """Finds the first available WhatsApp channel in the workspace."""
    url = f"{BIRD_API_BASE.rstrip('/')}/workspaces/{BIRD_WORKSPACE_ID}/channels"
    print(f"Searching for WhatsApp channels in workspace {BIRD_WORKSPACE_ID}...")
    
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url, headers=HEADERS)
            if response.status_code != 200:
                print(f"Failed to list channels. Status: {response.status_code}")
                print(response.text)
                return None
            
            data = response.json()
            results = data.get("results", [])
            
            for channel in results:
                # Inspect channel object for 'platform' or similar identifier
                # Note: The field name might vary, checking common ones
                platform = channel.get("platform") or channel.get("type")
                name = channel.get("name")
                print(f" - Found channel: {name} (ID: {channel['id']}, Platform: {platform})")
                
                if platform and "whatsapp" in platform.lower():
                    return channel['id']
                    
    except Exception as e:
        print(f"Error fetching channels: {e}")
    
    return None

def send_whatsapp_message(channel_id, to_number, text_body):
    """Sends a text message via WhatsApp."""
    url = f"{BIRD_API_BASE.rstrip('/')}/workspaces/{BIRD_WORKSPACE_ID}/channels/{channel_id}/messages"
    
    payload = {
        "receiver": {
            "contacts": [
                {"identifierValue": to_number}
            ]
        },
        "body": {
            "type": "text",
            "text": {
                "text": text_body
            }
        }
    }
    
    print(f"\nSending message to {to_number} via channel {channel_id}...")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, headers=HEADERS, json=payload)
            print(f"Status: {response.status_code}")
            try:
                print("Response:", json.dumps(response.json(), indent=2))
            except:
                print("Response:", response.text)
                
            if response.status_code in [200, 201, 202]:
                print("\n✅ Message sent successfully!")
            else:
                print("\n❌ Failed to send message.")

    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    print("--- Bird WhatsApp Tester ---")
    
    # 1. auto-discover channel
    channel_id = get_whatsapp_channel()
    
    if not channel_id:
        print("\nCould not automatically find a WhatsApp channel.")
        channel_id = input("Enter your WhatsApp Channel ID manually: ").strip()
        if not channel_id:
            print("No channel ID provided. Exiting.")
            sys.exit(1)
    else:
        print(f"\nUsing auto-discovered WhatsApp Channel ID: {channel_id}")

    # 2. Ask for destination
    to_number = input("\nEnter destination number (E.164 format, e.g. +56912345678): ").strip()
    if not to_number:
        print("No number provided. Exiting.")
        sys.exit(1)

    # 3. Message content
    # Note: If passing 'text' fails because of 24h window, try template.
    # But for a basic connectivity test, we try text first or warn user.
    message = "Hello from Bird API Python Client! 🐦"
    
    print("\nNote: Standard text messages may fail if outside the 24h user-initiated window.")
    print("If you get an error, you might need to send a Template message instead.")
    
    confirm = input(f"Send '{message}' to {to_number}? [y/N]: ").lower()
    if confirm == 'y':
        send_whatsapp_message(channel_id, to_number, message)
    else:
        print("Cancelled.")
