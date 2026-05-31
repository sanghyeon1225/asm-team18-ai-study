from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


_SESSIONS: dict[str, dict[str, Any]] = {}
_LOCK = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_title(analysis: dict[str, Any]) -> str:
    company_name = str(analysis.get("company_name") or "재무 분석").strip()
    year = analysis.get("year")
    report_name = str(analysis.get("report_name") or "").strip()
    parts = [company_name]
    if year:
        parts.append(str(year))
    if report_name:
        parts.append(report_name)
    return " ".join(parts)


def _summarize_session(session_id: str, session: dict[str, Any]) -> dict[str, Any]:
    analysis = session.get("analysis") or {}
    messages = session.get("messages") or []
    return {
        "session_id": session_id,
        "title": session.get("title") or _build_title(analysis),
        "company_name": analysis.get("company_name"),
        "year": analysis.get("year"),
        "report_name": analysis.get("report_name"),
        "message_count": len(messages),
        "created_at": session.get("created_at", ""),
        "updated_at": session.get("updated_at", ""),
    }


def create_session(analysis: dict[str, Any]) -> str:
    session_id = uuid4().hex
    now = _now_iso()
    with _LOCK:
        _SESSIONS[session_id] = {
            "analysis": deepcopy(analysis),
            "messages": [],
            "title": _build_title(analysis),
            "created_at": now,
            "updated_at": now,
        }
    return session_id


def get_session(session_id: str) -> dict[str, Any] | None:
    with _LOCK:
        session = _SESSIONS.get(session_id)
        return deepcopy(session) if session is not None else None


def list_sessions() -> list[dict[str, Any]]:
    with _LOCK:
        summaries = [
            _summarize_session(session_id, session)
            for session_id, session in _SESSIONS.items()
        ]
    return sorted(summaries, key=lambda item: item.get("updated_at", ""), reverse=True)


def add_message(session_id: str, role: str, content: str) -> None:
    if role not in {"user", "assistant"}:
        raise ValueError("role must be either 'user' or 'assistant'.")

    with _LOCK:
        if session_id not in _SESSIONS:
            raise KeyError(session_id)
        _SESSIONS[session_id]["messages"].append(
            {
                "role": role,
                "content": content,
            }
        )
        _SESSIONS[session_id]["updated_at"] = _now_iso()


def get_messages(session_id: str) -> list[dict[str, str]]:
    with _LOCK:
        if session_id not in _SESSIONS:
            raise KeyError(session_id)
        return deepcopy(_SESSIONS[session_id]["messages"])


def clear_sessions() -> None:
    with _LOCK:
        _SESSIONS.clear()
