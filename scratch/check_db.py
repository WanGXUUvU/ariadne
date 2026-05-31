import sqlite3
import json

db_path = "agent_session.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

session_id = '65d78bb0f7b6497385003646112989bc'

print("=== 1. LATEST RUN ===")
cursor.execute(
    "SELECT run_id, run_status, user_input, reply, created_at, finished_at FROM session_runs WHERE session_id = ? ORDER BY id DESC LIMIT 1;",
    (session_id,)
)
run = cursor.fetchone()
if not run:
    print("No runs found.")
    conn.close()
    exit()

run_id, status, user_input, reply, created_at, finished_at = run
print(f"Run ID: {run_id}")
print(f"Status: {status}")
print(f"Created At: {created_at}")
print(f"Finished At: {finished_at}")
print(f"User Input: {user_input}")
print(f"Reply: {reply[:300]}...")

print("\n=== 2. LATEST RUN EVENTS ===")
cursor.execute(
    "SELECT event_index, type, tool_name, tool_call_id, content FROM session_run_events WHERE run_id = ? ORDER BY event_index ASC;",
    (run_id,)
)
events = cursor.fetchall()
for ev in events:
    print(f"[{ev[0]}] Type: {ev[1]} | Tool: {ev[2]} | CallID: {ev[3]} | Content: {ev[4][:150]}")

print("\n=== 3. PENDING APPROVALS ===")
cursor.execute(
    "SELECT id, tool_name, status, event_index, batch_id FROM pending_approvals WHERE session_id = ?;",
    (session_id,)
)
approvals = cursor.fetchall()
for app in approvals:
    print(f"App ID: {app[0]} | Tool: {app[1]} | Status: {app[2]} | Index: {app[3]} | BatchID: {app[4]}")

conn.close()
