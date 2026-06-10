"""
examples/usage.py
~~~~~~~~~~~~~~~~~
Demonstrates common patterns for session_history_saver.
Run:  python examples/usage.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from session_history_saver import (
    SessionTracker,
    SessionHistoryConfig,
    to_json, to_csv, to_markdown, to_plain_text, save_to_file,
)


# ─────────────────────────────────────────────
# 1. Basic SQLite usage
# ─────────────────────────────────────────────
print("=" * 60)
print("1. BASIC SQLITE USAGE")
print("=" * 60)

tracker = SessionTracker(
    backend="sqlite",
    db_path="/tmp/demo_history.db",
    default_project_id="demo-project",
)

session = tracker.start_session(user_id="alice", title="Support Chat")
tracker.add_user_message(session.session_id, "Hi, I need help with my order.")
tracker.add_assistant_message(
    session.session_id,
    "Of course! Please share your order number.",
    tokens=12, model="claude-3-sonnet", latency_ms=340.5
)
tracker.add_user_message(session.session_id, "It's #ORD-99182.")
tracker.add_assistant_message(
    session.session_id,
    "Found it! Your order ships tomorrow.",
    tokens=8, model="claude-3-sonnet", latency_ms=210.0
)
tracker.end_session(session.session_id)

stats = tracker.stats(session.session_id)
print(f"Session ID   : {session.session_id}")
print(f"Messages     : {stats['message_count']}")
print(f"Total tokens : {stats['total_tokens']}")
print()


# ─────────────────────────────────────────────
# 2. Context manager
# ─────────────────────────────────────────────
print("=" * 60)
print("2. CONTEXT MANAGER")
print("=" * 60)

with tracker.track_session(user_id="bob", tags=["onboarding"]) as s:
    tracker.add_user_message(s.session_id, "How do I reset my password?")
    tracker.add_assistant_message(s.session_id, "Click 'Forgot password' on the login page.")

print(f"Session {s.session_id[:8]}… ended automatically.")
print()


# ─────────────────────────────────────────────
# 3. Decorator
# ─────────────────────────────────────────────
print("=" * 60)
print("3. DECORATOR")
print("=" * 60)

@tracker.track(project_id="demo-project")
def answer_query(question: str) -> str:
    # In a real app this would call an LLM
    return f"Auto-answer: {question[::-1]}"

result = answer_query("What is the capital of France?")
print(f"Result: {result}")
print()


# ─────────────────────────────────────────────
# 4. JSON backend (no DB required)
# ─────────────────────────────────────────────
print("=" * 60)
print("4. JSON BACKEND")
print("=" * 60)

json_tracker = SessionTracker(backend="json", storage_dir="/tmp/session_files")
js = json_tracker.start_session(user_id="carol")
json_tracker.add_user_message(js.session_id, "JSON backend message")
json_tracker.end_session(js.session_id)
print(f"Saved to /tmp/session_files/{js.session_id}.json")
print()


# ─────────────────────────────────────────────
# 5. Listing & searching
# ─────────────────────────────────────────────
print("=" * 60)
print("5. LISTING & SEARCHING")
print("=" * 60)

sessions = tracker.list_sessions(project_id="demo-project", limit=5)
print(f"Sessions in 'demo-project': {len(sessions)}")

results = tracker.search("order")
print(f"Search 'order' → {len(results)} session(s) found")
print()


# ─────────────────────────────────────────────
# 6. Export formats
# ─────────────────────────────────────────────
print("=" * 60)
print("6. EXPORT FORMATS")
print("=" * 60)

loaded = tracker.get_session(session.session_id)

md = to_markdown(loaded, include_metadata=True)
save_to_file(md, "/tmp/session_export.md")
print("Markdown saved → /tmp/session_export.md")

csv_str = to_csv([loaded])
save_to_file(csv_str, "/tmp/session_export.csv")
print("CSV saved     → /tmp/session_export.csv")

plain = to_plain_text(loaded)
print("\nPlain text preview:")
print(plain[:300])
print()


# ─────────────────────────────────────────────
# 7. Config via environment variables
# ─────────────────────────────────────────────
print("=" * 60)
print("7. CONFIG FROM ENV / CONFIG OBJECT")
print("=" * 60)

import os
os.environ["SHS_BACKEND"] = "memory"
os.environ["SHS_DEFAULT_PROJECT"] = "env-project"

cfg = SessionHistoryConfig()
env_tracker = SessionTracker(**cfg.to_tracker_kwargs())
es = env_tracker.start_session(user_id="dave")
env_tracker.add_user_message(es.session_id, "Config from env!")
env_tracker.end_session(es.session_id)

global_stats = env_tracker.stats()
print(f"Sessions in memory: {global_stats['total_sessions']}")
print(f"Default project   : {cfg.default_project_id}")
print()

print("✅  All examples completed.")
