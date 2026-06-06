"""추가 질문 채팅 UI: 메시지 렌더링, 추천 질문 칩, 환영 메시지.

칩 클릭과 직접 타이핑 모두 동일한 POST /chat 경로를 거치므로, 백엔드의
투자 추천 차단 가드레일이 우회 없이 그대로 적용된다.
"""
from __future__ import annotations

import html
from typing import Any

import streamlit as st

from ui.api import post_json
from ui.scroll import render_chat_bottom_anchor
from ui.session import cache_session, upsert_session_summary


def render_user_chat_message(content: str) -> None:
    safe_content = html.escape(content or "").replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="gt-user-wrapper">
            <div class="gt-user-bubble">{safe_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_assistant_chat_message(content: str) -> None:
    avatar_col, body_col = st.columns([0.06, 0.94])
    with avatar_col:
        st.markdown('<div class="gt-assistant-avatar">공</div>', unsafe_allow_html=True)
    with body_col:
        st.markdown('<div class="gt-assistant-name">공시톡 AI</div>', unsafe_allow_html=True)
        st.markdown(content or "")


def render_thinking_message() -> None:
    avatar_col, body_col = st.columns([0.06, 0.94])
    with avatar_col:
        st.markdown('<div class="gt-assistant-avatar">공</div>', unsafe_allow_html=True)
    with body_col:
        st.markdown('<div class="gt-assistant-name">공시톡 AI</div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div class="gt-thinking-pill">
                <span>생각하는 중</span>
                <span class="gt-typing-dots" aria-hidden="true">
                    <span class="gt-typing-dot"></span>
                    <span class="gt-typing-dot"></span>
                    <span class="gt-typing-dot"></span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_messages(messages: list[dict[str, str]], *, show_thinking: bool = False) -> None:
    if not messages and not show_thinking:
        return

    with st.container():
        for index, message in enumerate(messages):
            if index > 0:
                st.markdown('<div class="gt-message-spacer"></div>', unsafe_allow_html=True)

            if message.get("role") == "user":
                render_user_chat_message(message.get("content", ""))
            else:
                render_assistant_chat_message(message.get("content", ""))

        if show_thinking:
            st.markdown('<div class="gt-message-spacer"></div>', unsafe_allow_html=True)
            render_thinking_message()


def build_suggested_questions(context: dict[str, Any]) -> list[str]:
    """초보자가 바로 누를 수 있는 맥락 기반 추천 질문을 만든다."""
    questions = [
        "이 회사 재무 상태를 한마디로 요약해줘",
        "부채가 많은 편이야? 쉽게 알려줘",
        "영업이익률이 좋은 건지 설명해줘",
    ]
    if context.get("previous_data_available"):
        questions.append("전년도랑 비교하면 뭐가 달라졌어?")
    if context.get("risk_signals"):
        questions.append("표시된 위험 신호가 무슨 뜻인지 알려줘")
    return questions


def render_followup_header() -> None:
    st.markdown(
        """
        <div class="gt-chat-header">
            <div class="gt-chat-header-icon">💬</div>
            <div>
                <div class="gt-chat-header-title">공시톡 AI에게 물어보기</div>
                <div class="gt-chat-header-sub">분석된 재무 데이터 안에서만 답해드려요 · 투자 추천은 제공하지 않습니다</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_chat_welcome(context: dict[str, Any]) -> None:
    """채팅이 비어 있을 때 봇이 먼저 건네는 환영 메시지."""
    company_name = str(context.get("company_name") or "이 기업").strip()
    avatar_col, body_col = st.columns([0.06, 0.94])
    with avatar_col:
        st.markdown('<div class="gt-assistant-avatar">공</div>', unsafe_allow_html=True)
    with body_col:
        st.markdown('<div class="gt-assistant-name">공시톡 AI</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="gt-welcome-text">
                <b>{html.escape(company_name)}</b> 분석을 마쳤어요! ✅<br>
                위 결과에서 궁금한 점을 편하게 물어보세요.
                무엇을 물어볼지 막막하다면 아래 추천 질문을 눌러도 좋아요. 😊
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_suggested_questions(context: dict[str, Any]) -> str | None:
    """추천 질문 칩을 그리고, 클릭된 질문 문자열을 반환한다(없으면 None)."""
    questions = build_suggested_questions(context)
    if not questions:
        return None

    st.markdown('<div class="gt-chip-label">💡 이런 걸 물어볼 수 있어요</div>', unsafe_allow_html=True)
    clicked: str | None = None
    columns = st.columns(2)
    for index, question in enumerate(questions):
        with columns[index % 2]:
            if st.button(question, key=f"gt-chip-{index}", use_container_width=True):
                clicked = question
    return clicked


def submit_followup_question(question: str, session_id: str, chat_area: Any) -> None:
    """타이핑 질문과 추천 질문 칩이 공유하는 단일 처리 경로."""
    messages = st.session_state.setdefault("messages", [])
    pending_messages = [
        *messages,
        {"role": "user", "content": question},
    ]
    st.session_state["messages"] = pending_messages
    with chat_area.container():
        render_chat_messages(pending_messages, show_thinking=True)

    try:
        with st.spinner("공시톡 AI가 저장된 분석 결과를 확인하고 있습니다..."):
            result = post_json(
                "/chat",
                {
                    "session_id": session_id,
                    "question": question,
                },
            )
        st.session_state["session_id"] = result["session_id"]
        messages = result.get("messages", st.session_state["messages"])
        st.session_state["messages"] = messages
        analysis = st.session_state.get("last_analysis") or {}
        cache_session(result["session_id"], analysis, messages)
        upsert_session_summary(result["session_id"], analysis, messages)
        st.session_state["scroll_to_chat"] = True
        st.rerun()
    except Exception as exc:
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": f"추가 질문 답변을 생성하지 못했습니다. {exc}",
            }
        )
        st.session_state["scroll_to_chat"] = True
        st.rerun()


def render_followup_area() -> None:
    context = st.session_state.get("last_analysis")
    session_id = st.session_state.get("session_id")
    if not context or not session_id:
        return

    st.divider()
    render_followup_header()

    messages = st.session_state.setdefault("messages", [])
    chat_area = st.empty()

    # 추천 질문 칩과 입력창 중 어디서 질문이 들어와도 같은 경로로 처리한다.
    clicked_question = render_suggested_questions(context)
    typed_question = st.chat_input("분석 결과에 대해 질문해보세요. 예: 이 회사 부채가 많은 편이야?")
    question = typed_question or clicked_question

    if not question:
        with chat_area.container():
            if messages:
                render_chat_messages(messages)
            else:
                render_chat_welcome(context)
            render_chat_bottom_anchor()
        return

    submit_followup_question(question, session_id, chat_area)
