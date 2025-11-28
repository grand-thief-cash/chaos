"""
Test script to verify parent task finalize callback behavior.

Usage:
    cd C:/Users/gaoc3/projects/chaos/app/projects/artemis
    python scripts/test_parent_finalize.py
"""

from artemis.core.config import init_config
from artemis.core.task_engine import TaskEngine

# Initialize config
init_config()

# Create engine
engine = TaskEngine()

# Test case: top-level parent task (should trigger finalize_success)
print("\n=== Test 1: Top-level parent task (a_share_pull_parent) ===")
res = engine.run(
    "a_share_pull_parent",
    {
        "period": "daily",
        "adjust": "",
        "codes": ["000001", "000002"],  # Only 2 symbols for quick test
        "_meta": {
            "run_id": 12345,
            "task_id": "test-parent-finalize",
            "exec_type": "SYNC",
            # If you have a real callback server running, add:
            # "callback_endpoints": {
            #     "progress": "/runs/12345/progress",
            #     "callback": "/runs/12345/callback"
            # }
        },
    },
    headers={
        # If you have a real cronjob service, fill these:
        # "X-Caller-IP": "127.0.0.1",
        # "X-Caller-Port": "8080"
    },
)

print(f"Task: {res['task_code']}")
print(f"Status: {res['status']}")
print(f"Duration: {res['duration_ms']} ms")
print(f"Children: {res['stats'].get('children_completed', 0)}/{res['stats'].get('children_total', 0)}")
print(f"Error: {res.get('error')}")

# Expected logs in console:
# - parent: task_start
# - parent: child_start (x2)
# - child: execute logs (akshare mock)
# - child: sink logs
# - parent: child_success (x2)
# - parent: parent_progress (current=1/2, then 2/2)
# - parent: task_success
# - engine: callback_finalize_success  <-- THIS IS THE KEY LOG
#
# If no callback server is running, you'll see warnings about HTTP errors, but that's expected.

print("\n=== Test completed ===")
print("Check logs above for 'callback_finalize_success' event.")
print("If you see it, then finalize callback is working!")

