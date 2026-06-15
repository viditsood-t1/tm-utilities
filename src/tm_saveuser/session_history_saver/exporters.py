"""
Export utilities — convert sessions to JSON, CSV, JSONL, Markdown, or plain text.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import List, Optional, Union

from .models import Session


def to_json(session: Session, indent: int = 2) -> str:
    """Serialise a session to a JSON string."""
    return json.dumps(session.to_dict(), indent=indent, ensure_ascii=False)


def to_jsonl(sessions: List[Session]) -> str:
    """Serialise multiple sessions to newline-delimited JSON (JSONL)."""
    lines = [json.dumps(s.to_dict(), ensure_ascii=False) for s in sessions]
    return "\n".join(lines)


def to_csv(sessions: List[Session]) -> str:
    """
    Flatten sessions + messages to CSV rows.

    Columns: session_id, user_id, project_id, title, tags,
             message_id, role, content, timestamp, tokens, model, latency_ms, status
    """
    output = io.StringIO()
    fieldnames = [
        "session_id", "user_id", "project_id", "title", "tags",
        "message_id", "role", "content", "timestamp",
        "tokens", "model", "latency_ms", "status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for session in sessions:
        base = {
            "session_id": session.session_id,
            "user_id": session.user_id or "",
            "project_id": session.project_id or "",
            "title": session.title or "",
            "tags": ",".join(session.tags),
        }
        for msg in session.messages:
            row = {**base, **{
                "message_id": msg.message_id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tokens": msg.tokens or "",
                "model": msg.model or "",
                "latency_ms": msg.latency_ms or "",
                "status": msg.status,
            }}
            writer.writerow(row)
    return output.getvalue()


def to_markdown(session: Session, include_metadata: bool = False) -> str:
    """
    Render a session as a readable Markdown document.
    """
    lines: List[str] = []
    title = session.title or f"Session {session.session_id[:8]}"
    lines.append(f"# {title}\n")

    meta_items = [
        f"- **Session ID:** `{session.session_id}`",
        f"- **Created:** {session.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
    ]
    if session.user_id:
        meta_items.append(f"- **User:** {session.user_id}")
    if session.project_id:
        meta_items.append(f"- **Project:** {session.project_id}")
    if session.tags:
        meta_items.append(f"- **Tags:** {', '.join(session.tags)}")
    meta_items.append(f"- **Messages:** {session.message_count}")
    if session.total_tokens:
        meta_items.append(f"- **Total tokens:** {session.total_tokens:,}")

    lines.extend(meta_items)
    lines.append("")
    lines.append("---\n")
    lines.append("## Conversation\n")

    role_emoji = {"user": "👤", "assistant": "🤖", "system": "⚙️", "tool": "🔧"}
    for msg in session.messages:
        emoji = role_emoji.get(msg.role, "💬")
        ts = msg.timestamp.strftime("%H:%M:%S")
        lines.append(f"### {emoji} {msg.role.capitalize()} `[{ts}]`\n")
        lines.append(msg.content)
        lines.append("")
        if include_metadata and (msg.tokens or msg.model or msg.latency_ms):
            extras = []
            if msg.model:
                extras.append(f"model={msg.model}")
            if msg.tokens:
                extras.append(f"tokens={msg.tokens}")
            if msg.latency_ms:
                extras.append(f"latency={msg.latency_ms:.0f}ms")
            if extras:
                lines.append(f"> _{', '.join(extras)}_\n")

    return "\n".join(lines)


def to_plain_text(session: Session) -> str:
    """Render a session as plain text (useful for fine-tuning data prep)."""
    lines: List[str] = []
    for msg in session.messages:
        lines.append(f"[{msg.role.upper()}]: {msg.content}")
    return "\n".join(lines)


def save_to_file(content: str, path: Union[str, Path]) -> Path:
    """Write export content to a file and return the Path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return out
