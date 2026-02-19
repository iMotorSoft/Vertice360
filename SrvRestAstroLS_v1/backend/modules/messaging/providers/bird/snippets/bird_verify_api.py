import httpx
import sys

import globalVar

# Load configuration only through globalVar helpers/constants
BIRD_API_KEY = globalVar.get_env_str("BIRD_API_KEY_VERTICE360_DEV_DEBUG") or globalVar.get_env_str(
    "BIRD_API_KEY_VERTICE360_DEV"
)
BIRD_WORKSPACE_ID = globalVar.get_env_str("BIRD_WORKSPACE_ID")
BIRD_API_BASE = globalVar.get_env_str("BIRD_API_BASE", "https://api.bird.com")

if not BIRD_API_KEY:
    print("Error: BIRD_API_KEY_VERTICE360_DEV (or DEBUG) is not set.")
    sys.exit(1)

if not BIRD_WORKSPACE_ID:
    print("Warning: BIRD_WORKSPACE_ID is not set. Most endpoints will fail with 403.")

print(f"--- Bird API Verification ---")
print(f"Base URL: {BIRD_API_BASE}")
print(f"Workspace ID: {BIRD_WORKSPACE_ID}")

# Primary test endpoint
if BIRD_WORKSPACE_ID:
    test_url = f"{BIRD_API_BASE.rstrip('/')}/workspaces/{BIRD_WORKSPACE_ID}/channels"
    print(f"Testing Workspace Channels: {test_url}")
else:
    test_url = f"{BIRD_API_BASE.rstrip('/')}/me"
    print(f"Testing Generic Endpoint (likely to fail w/o ID): {test_url}")

headers = {
    "Authorization": f"AccessKey {BIRD_API_KEY}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}
if BIRD_WORKSPACE_ID:
    headers["X-Bird-Workspace-ID"] = BIRD_WORKSPACE_ID

try:
    with httpx.Client(timeout=10.0) as client:
        response = client.get(test_url, headers=headers)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            print("SUCCESS! Connection verified.")
            data = response.json()
            # print(f"Results: {data}")
        else:
            print("FAILED.")
            try:
                print(f"Error: {response.json()}")
            except Exception:
                print(f"Error: {response.text}")

            if response.status_code == 403 and not BIRD_WORKSPACE_ID:
                print("\nTip: Set BIRD_WORKSPACE_ID in your environment to fix 403 errors.")

except Exception as e:
    print(f"Exception during request: {e}")
