import requests
import sys

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    print(f"Testing AI Serving at: {ai_base_url}")
    
    # 1. Ping / Health check
    try:
        r = requests.get(ai_base_url, timeout=10)
        print("Root URL status:", r.status_code)
        print("Root response:", r.text[:200])
    except Exception as e:
        print("Root URL failed:", e)

    # 2. Create session
    session_url = f"{ai_base_url.rstrip('/')}/v1/session"
    print(f"\nCreating session at: {session_url}")
    try:
        r = requests.post(session_url, timeout=30)
        print("Status:", r.status_code)
        print("Response:", r.text)
        if r.status_code == 200:
            session_id = r.json().get("session_id")
            print("Session ID:", session_id)
            
            # Delete session
            delete_url = f"{ai_base_url.rstrip('/')}/v1/session/{session_id}"
            print(f"\nDeleting session at: {delete_url}")
            rd = requests.delete(delete_url, timeout=10)
            print("Delete status:", rd.status_code)
            print("Delete response:", rd.text)
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    main()
