"""세션 상태 관리: 캐시, 요약 목록, draft 세션, 최근 대화 사이드바.

st.session_state 기반 인메모리 상태만 다룬다. 영속 저장은 백엔드 책임이다.
"""
from __future__ import annotations

from typing import Any
from uuid import uuid4

import streamlit as st

from src.dart_client import REPORT_CODES
from src.logging_config import get_logger
from ui.api import get_json
from ui.config import DRAFT_SESSION_PREFIX
from ui.formatting import truncate_text


logger = get_logger(__name__)


def clear_current_session() -> None:
    for key in ("session_id", "last_analysis", "messages"):
        st.session_state.pop(key, None)


def build_session_title(context: dict[str, Any]) -> str:
    company_name = str(context.get("company_name") or "재무 분석").strip()
    year = context.get("year")
    report_name = str(context.get("report_name") or "").strip()
    parts = [company_name]
    if year:
        parts.append(str(year))
    if report_name:
        parts.append(report_name)
    return " ".join(parts)


def cache_session(session_id: str, analysis: dict[str, Any], messages: list[dict[str, str]]) -> None:
    cache = st.session_state.setdefault("loaded_sessions", {})
    cache[session_id] = {
        "session_id": session_id,
        "analysis": analysis,
        "messages": messages,
    }
    logger.debug("세션 캐시 저장 | 세션=%s | 메시지=%s개", session_id, len(messages))


def upsert_session_summary(
    session_id: str,
    analysis: dict[str, Any],
    messages: list[dict[str, str]],
) -> None:
    summaries = st.session_state.setdefault("session_summaries", [])
    existing = next((item for item in summaries if item.get("session_id") == session_id), {})
    summary = {
        "session_id": session_id,
        "title": existing.get("title") or build_session_title(analysis),
        "company_name": analysis.get("company_name"),
        "year": analysis.get("year"),
        "report_name": analysis.get("report_name"),
        "message_count": len(messages),
        "created_at": existing.get("created_at", ""),
        "updated_at": existing.get("updated_at", ""),
        "is_draft": bool(analysis.get("is_draft") or existing.get("is_draft")),
    }
    st.session_state["session_summaries"] = [
        summary,
        *[item for item in summaries if item.get("session_id") != session_id],
    ]


def remove_session_summary(session_id: str) -> None:
    summaries = st.session_state.setdefault("session_summaries", [])
    st.session_state["session_summaries"] = [
        item for item in summaries if item.get("session_id") != session_id
    ]


def remove_cached_session(session_id: str) -> None:
    st.session_state.setdefault("loaded_sessions", {}).pop(session_id, None)


def create_draft_session(company_name: str, bsns_year: int, report_name: str) -> str:
    draft_session_id = f"{DRAFT_SESSION_PREFIX}{uuid4().hex}"
    draft_context = {
        "company_name": company_name,
        "year": int(bsns_year),
        "report_name": report_name,
        "report_code": REPORT_CODES.get(report_name, ""),
        "is_draft": True,
    }
    st.session_state["session_id"] = draft_session_id
    st.session_state["messages"] = []
    st.session_state.pop("last_analysis", None)
    upsert_session_summary(draft_session_id, draft_context, [])
    logger.debug("임시 세션 생성 | 세션=%s | 기업=%s", draft_session_id, company_name)
    return draft_session_id


def cleanup_draft_session(session_id: str | None) -> None:
    if not session_id or not str(session_id).startswith(DRAFT_SESSION_PREFIX):
        return
    logger.debug("임시 세션 정리 | 세션=%s", session_id)
    remove_session_summary(session_id)
    remove_cached_session(session_id)
    if st.session_state.get("session_id") == session_id:
        clear_current_session()


def get_session_summaries() -> list[dict[str, Any]]:
    if "session_summaries" not in st.session_state:
        logger.debug("세션 목록 로드 | 백엔드 조회")
        st.session_state["session_summaries"] = get_json("/sessions", timeout=5).get("sessions", [])
    return st.session_state.get("session_summaries", [])


def load_session_from_backend(session_id: str) -> None:
    cached = st.session_state.setdefault("loaded_sessions", {}).get(session_id)
    if cached:
        logger.info("세션 열기 | 캐시 사용 | 세션=%s", session_id)
        st.session_state["session_id"] = cached["session_id"]
        st.session_state["last_analysis"] = cached.get("analysis") or {}
        st.session_state["messages"] = cached.get("messages", [])
        return

    logger.info("세션 열기 | 백엔드 조회 | 세션=%s", session_id)
    result = get_json(f"/sessions/{session_id}", timeout=10)
    analysis = result.get("analysis") or {}
    messages = result.get("messages", [])
    st.session_state["session_id"] = result["session_id"]
    st.session_state["last_analysis"] = analysis
    st.session_state["messages"] = messages
    cache_session(result["session_id"], analysis, messages)
    logger.info("세션 열기 완료 | 세션=%s | 메시지=%s개", session_id, len(messages))


def switch_to_session(session_id: str) -> None:
    if session_id == st.session_state.get("session_id"):
        return
    logger.info("세션 전환 | 세션=%s", session_id)
    load_session_from_backend(session_id)
    st.rerun()


def format_session_button_label(session: dict[str, Any], *, active: bool = False) -> str:
    title = str(session.get("title") or "이전 분석")
    if session.get("is_draft"):
        prefix = "분석 중 · "
    else:
        prefix = "현재 · " if active else ""
    return f"{prefix}{truncate_text(title)}"


def render_session_history_sidebar() -> None:
    st.divider()
    if st.button("+ 새 분석", width="stretch", key="new_analysis_button"):
        clear_current_session()
        st.rerun()

    try:
        sessions = get_session_summaries()
    except Exception:
        st.caption("대화 기록을 불러오지 못했습니다.")
        return

    st.markdown('<div class="gt-history-header">최근 대화</div>', unsafe_allow_html=True)
    if not sessions:
        st.caption("아직 저장된 대화가 없습니다.")
        return

    active_session_id = st.session_state.get("session_id")
    for session in sessions[:20]:
        session_id = str(session.get("session_id") or "")
        if not session_id:
            continue

        is_active = session_id == active_session_id
        is_draft = bool(session.get("is_draft"))
        clicked = st.button(
            format_session_button_label(session, active=is_active),
            key=f"session_history_{session_id}",
            width="stretch",
            disabled=is_active or is_draft,
            type="primary" if is_active else "secondary",
        )
        if clicked:
            try:
                switch_to_session(session_id)
            except Exception as exc:
                st.error(f"대화 기록을 불러오지 못했습니다. {exc}")
