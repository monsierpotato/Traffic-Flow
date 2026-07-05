import requests
import json

BASE = "http://localhost:8000"

# Test 1: Dashboard
r = requests.get(f"{BASE}/api/v1/dashboard/stats", timeout=30)
print("=== Dashboard ===")
print("Status:", r.status_code)
data = r.json()
print("Total tasks:", data.get("total_tasks"))
print("Completed:", data.get("completed_tasks"))
print("Failed:", data.get("failed_tasks"))
print("Processing:", data.get("processing_tasks"))
print("Vehicle totals:", data.get("vehicle_totals_by_type"))
print()

# Test 2: Check recent tasks
if data.get("recent_tasks"):
    for t in data["recent_tasks"]:
        print(f"  Task {t['task_id'][:8]}... status={t['status']} progress={t['progress']}")

    # Test 3: Get result for a completed task
    for t in data["recent_tasks"]:
        if t["status"] == "completed":
            tid = t["task_id"]
            r2 = requests.get(f"{BASE}/api/v1/tasks/result/{tid}", timeout=30)
            print()
            print(f"=== Result for {tid[:8]}... ===")
            print("Status:", r2.status_code)
            result = r2.json()
            print(json.dumps(result, indent=2, default=str)[:800])
            break
