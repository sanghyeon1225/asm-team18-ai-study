from __future__ import annotations

import html
import os
from typing import Any
from uuid import uuid4

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from requests import RequestException

from src.dart_client import REPORT_CODES
from src.financial_analyzer import format_ratio
from src.safety import SAFETY_DISCLAIMER


load_dotenv()

DEFAULT_BACKEND_URL = "http://localhost:8000"
BACKEND_URL = os.getenv("GONGSITALK_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
DRAFT_SESSION_PREFIX = "draft-"

NUMBER_LABELS = {
    "revenue": "매출액",
    "operating_profit": "영업이익",
    "net_income": "당기순이익",
    "assets": "자산총계",
    "liabilities": "부채총계",
    "equity": "자본총계",
}

RATIO_LABELS = {
    "operating_margin": "영업이익률",
    "net_margin": "순이익률",
    "roe": "ROE",
    "debt_ratio": "부채비율",
    "equity_ratio": "자기자본비율",
}

GROWTH_LABELS = {
    "revenue_growth": ("revenue", "매출액 증가율"),
    "operating_profit_growth": ("operating_profit", "영업이익 증가율"),
    "net_income_growth": ("net_income", "당기순이익 증가율"),
    "assets_growth": ("assets", "자산총계 증가율"),
    "liabilities_growth": ("liabilities", "부채총계 증가율"),
    "equity_growth": ("equity", "자본총계 증가율"),
}

REPORT_OPTIONS = ["사업보고서", "반기", "1분기", "3분기"]


def api_url(path: str) -> str:
    return f"{BACKEND_URL}{path}"


def post_json(path: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    try:
        response = requests.post(api_url(path), json=payload, timeout=timeout)
    except RequestException as exc:
        raise RuntimeError(
            f"FastAPI 백엔드에 연결할 수 없습니다. 먼저 `uvicorn backend.main:app --reload --port 8000`을 실행해주세요. 상세: {exc}"
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("백엔드 응답을 JSON으로 해석하지 못했습니다.") from exc


def get_json(path: str, timeout: int = 30) -> dict[str, Any]:
    try:
        response = requests.get(api_url(path), timeout=timeout)
    except RequestException as exc:
        raise RuntimeError(
            f"FastAPI 백엔드에 연결할 수 없습니다. 먼저 `uvicorn backend.main:app --reload --port 8000`을 실행해주세요. 상세: {exc}"
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("백엔드 응답을 JSON으로 해석하지 못했습니다.") from exc


def format_amount_eok(value: int | float | None) -> str:
    if value is None:
        return "데이터 없음"
    return f"{float(value) / 100_000_000:,.2f}억 원"


def amount_to_eok(value: int | float | None) -> float | None:
    if value is None:
        return None
    return float(value) / 100_000_000


def build_numbers_table(numbers: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "항목": label,
                "금액": format_amount_eok(numbers.get(key)),
            }
            for key, label in NUMBER_LABELS.items()
        ]
    )


def build_ratios_table(ratios: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "항목": label,
                "비율": format_ratio(ratios.get(key)),
            }
            for key, label in RATIO_LABELS.items()
        ]
    )


def build_numbers_chart_data(numbers: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "항목": label,
            "금액(억 원)": amount_to_eok(numbers.get(key)),
        }
        for key, label in NUMBER_LABELS.items()
    ]
    chart_data = pd.DataFrame(rows).set_index("항목")
    chart_data["금액(억 원)"] = pd.to_numeric(chart_data["금액(억 원)"], errors="coerce")
    return chart_data


def build_comparison_chart_data(
    current_numbers: dict[str, Any],
    previous_numbers: dict[str, Any],
    current_year: int,
    previous_year: int,
) -> pd.DataFrame:
    rows = []
    for key, label in NUMBER_LABELS.items():
        rows.append(
            {
                "항목": label,
                f"{current_year}년": amount_to_eok(current_numbers.get(key)),
                f"{previous_year}년": amount_to_eok(previous_numbers.get(key)),
            }
        )
    chart_data = pd.DataFrame(rows).set_index("항목")
    chart_data[f"{current_year}년"] = pd.to_numeric(chart_data[f"{current_year}년"], errors="coerce")
    chart_data[f"{previous_year}년"] = pd.to_numeric(chart_data[f"{previous_year}년"], errors="coerce")
    return chart_data


def format_growth(value: float | None, previous_data_available: bool) -> str:
    if not previous_data_available:
        return "전년도 비교 데이터 없음"
    if value is None:
        return "추가 확인 필요"
    return format_ratio(value)


def build_growth_table(
    current_numbers: dict[str, Any],
    previous_numbers: dict[str, Any] | None,
    growth: dict[str, Any],
    previous_data_available: bool,
) -> pd.DataFrame:
    rows = []
    for growth_key, (number_key, label) in GROWTH_LABELS.items():
        rows.append(
            {
                "항목": label,
                "현재 연도": format_amount_eok(current_numbers.get(number_key)),
                "전년도": (
                    format_amount_eok(previous_numbers.get(number_key))
                    if previous_data_available and previous_numbers is not None
                    else "전년도 비교 데이터 없음"
                ),
                "전년 대비": format_growth(growth.get(growth_key), previous_data_available),
            }
        )
    return pd.DataFrame(rows)


def strip_disclaimer_from_explanation(explanation: str) -> str:
    if not explanation:
        return ""

    lines: list[str] = []
    for line in explanation.splitlines():
        stripped = line.strip()
        if SAFETY_DISCLAIMER in stripped:
            while lines and not lines[-1].strip():
                lines.pop()
            if lines:
                previous = lines[-1].strip().lstrip("#").strip()
                if "면책" in previous:
                    lines.pop()
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def render_chat_styles() -> None:
    st.markdown(
        """
        <style>
        .gt-message-spacer {
            height: 0.85rem;
        }
        .gt-user-wrapper,
        .gt-user-wrapper * {
            box-sizing: border-box;
        }
        .gt-user-wrapper {
            display: flex;
            width: 100%;
            justify-content: flex-end;
            height: auto;
            min-height: 0;
        }
        .gt-user-bubble {
            display: inline-block;
            width: fit-content;
            max-width: min(58%, 520px);
            padding: 0.5rem 0.78rem;
            border-radius: 1.12rem;
            background: #2563eb;
            color: #ffffff;
            height: auto;
            min-height: 0;
            line-height: 1.45;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font-size: 0.95rem;
            text-align: left;
            box-shadow: none;
        }
        .gt-assistant-avatar {
            box-sizing: border-box;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            margin-top: 0.2rem;
            border-radius: 999px;
            background: #0f172a;
            color: white;
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1;
        }
        .gt-assistant-body {
            color: #0f172a;
            line-height: 1.65;
        }
        .gt-assistant-name {
            margin-bottom: 0.18rem;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .gt-thinking-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            width: auto;
            max-width: 100%;
            height: auto;
            min-height: 2rem;
            padding: 0.48rem 0.72rem;
            overflow: hidden;
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 999px;
            background: #f8fafc;
            color: #475569;
            font-size: 0.94rem;
            font-weight: 600;
            line-height: 1.2;
        }
        .gt-typing-dots {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.18rem;
            flex: 0 0 auto;
            height: 0.5rem;
            line-height: 1;
        }
        .gt-typing-dot {
            display: block;
            flex: 0 0 0.28rem;
            width: 0.28rem;
            height: 0.28rem;
            margin: 0;
            border-radius: 999px;
            background: #94a3b8;
            animation: gongsitalkPulse 1.25s infinite ease-in-out;
        }
        .gt-typing-dot:nth-child(2) {
            animation-delay: 0.18s;
        }
        .gt-typing-dot:nth-child(3) {
            animation-delay: 0.36s;
        }
        @keyframes gongsitalkPulse {
            0%, 80%, 100% {
                opacity: 0.35;
                transform: translateY(0);
            }
            40% {
                opacity: 1;
                transform: translateY(-1px);
            }
        }
        @media (max-width: 700px) {
            .gt-user-bubble {
                max-width: 86%;
            }
        }
        section[data-testid="stSidebar"] div.stButton > button,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button {
            min-height: 2.28rem;
            padding: 0.44rem 0.62rem;
            border-radius: 0.55rem;
            justify-content: flex-start;
            text-align: left;
            white-space: normal;
            font-size: 0.88rem;
            font-weight: 500;
            line-height: 1.25;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        section[data-testid="stSidebar"] div.stButton > button p,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button p {
            font-size: inherit;
            font-weight: inherit;
            line-height: inherit;
            color: inherit;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:hover {
            border-color: rgba(37, 99, 235, 0.35);
            background: #f8fafc;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled),
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled),
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled),
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled) {
            justify-content: center;
            border-color: #2563eb !important;
            background: #2563eb !important;
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):focus {
            border-color: #1d4ed8 !important;
            background: #1d4ed8 !important;
            color: #ffffff !important;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):hover *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):focus *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):hover *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):focus * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:disabled,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:disabled {
            opacity: 1;
            border-color: rgba(37, 99, 235, 0.26) !important;
            background: #eef2ff !important;
            color: #172554 !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:disabled *,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:disabled * {
            color: #172554 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[kind],
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[type="submit"],
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[data-testid] {
            justify-content: center !important;
            border-color: #2563eb !important;
            background: #2563eb !important;
            background-color: #2563eb !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:focus,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:active {
            border-color: #1d4ed8 !important;
            background: #1d4ed8 !important;
            background-color: #1d4ed8 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:focus *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:active * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .gt-history-header {
            margin: 0.65rem 0 0.36rem;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
        }
        .gt-analysis-overlay {
            position: static;
            box-sizing: border-box;
            width: 100%;
            max-height: none;
            overflow: visible;
            padding: 0.25rem 0 1rem;
            background: transparent;
            color: #0f172a;
        }
        .gt-analysis-overlay-inner {
            box-sizing: border-box;
            width: min(920px, 100%);
            margin: 0;
            padding: 1rem 1.1rem;
            border: 1px solid rgba(37, 99, 235, 0.18);
            border-radius: 0.9rem;
            background: rgba(255, 255, 255, 0.96);
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.1);
        }
        .gt-analysis-kicker {
            margin: 0 0 0.22rem;
            color: #2563eb;
            font-size: 0.78rem;
            font-weight: 800;
        }
        .gt-analysis-heading {
            margin: 0 0 0.3rem;
            font-size: 1.12rem;
            font-weight: 800;
            line-height: 1.28;
        }
        .gt-analysis-copy {
            margin: 0;
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .gt-analysis-steps {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem 0.8rem;
            width: 100%;
            margin-top: 0.75rem;
        }
        .gt-analysis-step {
            display: flex;
            align-items: center;
            gap: 0.42rem;
            min-height: 1.4rem;
            color: #1e293b;
            font-size: 0.82rem;
            line-height: 1.25;
        }
        .gt-analysis-step-dot {
            flex: 0 0 0.46rem;
            width: 0.46rem;
            height: 0.46rem;
            border-radius: 999px;
            background: #2563eb;
            animation: gongsitalkPulse 1.25s infinite ease-in-out;
        }
        @media (max-width: 700px) {
            .gt-analysis-overlay {
                width: 100%;
            }
            .gt-analysis-overlay-inner {
                padding: 0.85rem 0.9rem;
                border-radius: 0.75rem;
            }
            .gt-analysis-steps {
                display: grid;
                gap: 0.4rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def clear_current_session() -> None:
    for key in ("session_id", "last_analysis", "messages"):
        st.session_state.pop(key, None)


def render_top_anchor() -> None:
    st.markdown('<div id="gongsitalk-page-top"></div>', unsafe_allow_html=True)


def scroll_to_top_once() -> None:
    if not st.session_state.pop("scroll_to_top", False):
        return
    force_scroll_to_top()


def force_scroll_to_top() -> None:
    components.html(
        """
        <script>
        const scrollTop = () => {
            const parentWindow = window.parent;
            const doc = parentWindow.document;
            const anchor = doc.getElementById("gongsitalk-page-top");
            if (anchor) {
                anchor.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" });
            }
            try {
                parentWindow.scrollTo({ top: 0, left: 0, behavior: "auto" });
            } catch (error) {}
            const selectors = [
                "html",
                "body",
                "[data-testid='stAppViewContainer']",
                "[data-testid='stMain']",
                "section.main",
                ".main"
            ];
            selectors
                .map((selector) => doc.querySelector(selector))
                .filter(Boolean)
                .forEach((element) => {
                    element.scrollTop = 0;
                    element.scrollLeft = 0;
                });
        };
        [0, 40, 100, 220, 420, 800].forEach((delay) => setTimeout(scrollTop, delay));
        </script>
        """,
        height=0,
    )


def analysis_context_from_response(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"session_id", "messages"}
    }


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
    return draft_session_id


def cleanup_draft_session(session_id: str | None) -> None:
    if not session_id or not str(session_id).startswith(DRAFT_SESSION_PREFIX):
        return
    remove_session_summary(session_id)
    remove_cached_session(session_id)
    if st.session_state.get("session_id") == session_id:
        clear_current_session()


def get_session_summaries() -> list[dict[str, Any]]:
    if "session_summaries" not in st.session_state:
        st.session_state["session_summaries"] = get_json("/sessions", timeout=5).get("sessions", [])
    return st.session_state.get("session_summaries", [])


def load_session_from_backend(session_id: str) -> None:
    cached = st.session_state.setdefault("loaded_sessions", {}).get(session_id)
    if cached:
        st.session_state["session_id"] = cached["session_id"]
        st.session_state["last_analysis"] = cached.get("analysis") or {}
        st.session_state["messages"] = cached.get("messages", [])
        return

    result = get_json(f"/sessions/{session_id}", timeout=10)
    analysis = result.get("analysis") or {}
    messages = result.get("messages", [])
    st.session_state["session_id"] = result["session_id"]
    st.session_state["last_analysis"] = analysis
    st.session_state["messages"] = messages
    cache_session(result["session_id"], analysis, messages)


def switch_to_session(session_id: str) -> None:
    if session_id == st.session_state.get("session_id"):
        return
    load_session_from_backend(session_id)
    st.rerun()


def render_analysis_overlay(company_name: str, bsns_year: int, report_name: str) -> None:
    safe_company = html.escape(company_name)
    safe_report = html.escape(report_name)
    st.markdown(
        f"""
        <div class="gt-analysis-overlay" role="status" aria-live="polite">
            <div class="gt-analysis-overlay-inner">
                <div class="gt-analysis-kicker">새 분석 진행 중</div>
                <h2 class="gt-analysis-heading">{safe_company} {bsns_year}년 {safe_report}</h2>
                <p class="gt-analysis-copy">
                    공시 데이터를 가져오고 재무 수치, 비율, AI 해설을 차례로 준비하고 있습니다.
                </p>
                <div class="gt-analysis-steps">
                    <div class="gt-analysis-step">
                        <span class="gt-analysis-step-dot"></span>
                        <span>기업 고유번호와 분석 조건을 확인합니다.</span>
                    </div>
                    <div class="gt-analysis-step">
                        <span class="gt-analysis-step-dot"></span>
                        <span>DART 주요계정 데이터를 조회합니다.</span>
                    </div>
                    <div class="gt-analysis-step">
                        <span class="gt-analysis-step-dot"></span>
                        <span>핵심 재무 수치와 재무비율을 계산합니다.</span>
                    </div>
                    <div class="gt-analysis-step">
                        <span class="gt-analysis-step-dot"></span>
                        <span>AI 해설과 새 대화 세션을 준비합니다.</span>
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_analysis_with_progress(
    company_name: str,
    bsns_year: int,
    report_name: str,
    draft_session_id: str | None = None,
) -> None:
    render_analysis_overlay(company_name, bsns_year, report_name)

    try:
        result = post_json(
            "/analysis",
            {
                "company_name": company_name,
                "year": int(bsns_year),
                "report_code": REPORT_CODES[report_name],
                "report_name": report_name,
            },
        )
    except Exception:
        raise

    st.session_state["session_id"] = result["session_id"]
    analysis = analysis_context_from_response(result)
    messages = result.get("messages", [])
    st.session_state["last_analysis"] = analysis
    st.session_state["messages"] = messages
    cleanup_draft_session(draft_session_id)
    st.session_state["session_id"] = result["session_id"]
    cache_session(result["session_id"], analysis, messages)
    upsert_session_summary(result["session_id"], analysis, messages)
    st.session_state["scroll_to_top"] = True
    st.rerun()


def queue_new_analysis(company_name: str, bsns_year: int, report_name: str) -> None:
    clear_current_session()
    draft_session_id = create_draft_session(company_name, int(bsns_year), report_name)
    st.session_state["pending_analysis_request"] = {
        "company_name": company_name,
        "bsns_year": int(bsns_year),
        "report_name": report_name,
        "draft_session_id": draft_session_id,
    }
    st.session_state["scroll_to_top"] = True
    st.rerun()


def truncate_text(value: str, limit: int = 30) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def format_session_button_label(session: dict[str, Any], *, active: bool = False) -> str:
    title = str(session.get("title") or "이전 분석")
    if session.get("is_draft"):
        prefix = "분석 중 · "
    else:
        prefix = "현재 · " if active else ""
    return f"{prefix}{truncate_text(title)}"


def render_session_history_sidebar() -> None:
    st.divider()
    if st.button("+ 새 분석", use_container_width=True, key="new_analysis_button"):
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
            use_container_width=True,
            disabled=is_active or is_draft,
            type="primary" if is_active else "secondary",
        )
        if clicked:
            try:
                switch_to_session(session_id)
            except Exception as exc:
                st.error(f"대화 기록을 불러오지 못했습니다. {exc}")


def render_candidate_info(context: dict[str, Any]) -> None:
    st.subheader("기업 후보/선택된 기업 정보")

    selected = context.get("selected_company") or {}
    selected_stock_code = selected.get("stock_code") or "비상장 또는 정보 없음"
    st.info(
        f"선택된 기업: {selected.get('corp_name', '-')}"
        f" / 고유번호: {selected.get('corp_code', '-')}"
        f" / 종목코드: {selected_stock_code}"
    )

    candidates = pd.DataFrame(context.get("candidate_companies") or [])
    if candidates.empty:
        return

    display_candidates = candidates.rename(
        columns={
            "corp_code": "고유번호",
            "corp_name": "기업명",
            "corp_eng_name": "영문명",
            "stock_code": "종목코드",
            "modify_date": "수정일",
        }
    )
    st.dataframe(display_candidates.head(10), use_container_width=True, hide_index=True)


def render_analysis_result(context: dict[str, Any]) -> None:
    render_candidate_info(context)

    left, right = st.columns(2)
    with left:
        st.subheader("핵심 재무 수치")
        st.dataframe(build_numbers_table(context["numbers"]), use_container_width=True, hide_index=True)

    with right:
        st.subheader("재무비율")
        st.dataframe(build_ratios_table(context["ratios"]), use_container_width=True, hide_index=True)

    st.subheader("핵심 재무 수치 시각화")
    st.bar_chart(build_numbers_chart_data(context["numbers"]))

    st.subheader("전년 대비 성장성")
    if not context.get("previous_data_available", False):
        st.info("전년도 비교 데이터 없음")
    st.dataframe(
        build_growth_table(
            context["numbers"],
            context.get("previous_numbers"),
            context.get("growth", {}),
            context.get("previous_data_available", False),
        ),
        use_container_width=True,
        hide_index=True,
    )

    if context.get("previous_data_available", False) and context.get("previous_numbers"):
        st.subheader("현재 연도 vs 전년도")
        st.bar_chart(
            build_comparison_chart_data(
                context["numbers"],
                context["previous_numbers"],
                int(context["year"]),
                int(context["previous_year"]),
            )
        )

    st.subheader("위험 신호")
    if context["risk_signals"]:
        for signal in context["risk_signals"]:
            st.warning(signal)
    else:
        st.success("현재 추출된 핵심 수치 기준으로는 주요 위험 신호가 뚜렷하게 표시되지 않았습니다. 전문 공시와 주석은 추가 확인이 필요합니다.")

    raw_accounts = context.get("raw_accounts") or []
    if raw_accounts:
        with st.expander("DART 주요계정 원본 일부 보기"):
            st.dataframe(pd.DataFrame(raw_accounts), use_container_width=True, hide_index=True)

    st.subheader("AI 분석 결과")
    explanation = strip_disclaimer_from_explanation(str(context.get("explanation") or ""))
    if explanation:
        st.markdown(explanation)
    st.caption(SAFETY_DISCLAIMER)


def render_followup_area() -> None:
    context = st.session_state.get("last_analysis")
    session_id = st.session_state.get("session_id")
    if not context or not session_id:
        return

    st.divider()
    st.subheader("추가 질문하기")
    st.caption("분석된 재무 데이터 안에서만 답변합니다. 매수/매도 판단이나 투자 추천은 제공하지 않습니다.")

    messages = st.session_state.setdefault("messages", [])
    chat_area = st.empty()

    question = st.chat_input("분석 결과에 대해 질문해보세요. 예: 이 회사 부채가 많은 편이야?")
    if not question:
        with chat_area.container():
            render_chat_messages(messages)
        return

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
        st.rerun()
    except Exception as exc:
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": f"추가 질문 답변을 생성하지 못했습니다. {exc}",
            }
        )
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="공시톡", page_icon="📊", layout="wide")
    render_chat_styles()
    render_top_anchor()
    st.title("📊 공시톡 - DART 재무제표 분석 챗봇")
    scroll_to_top_once()
    body = st.empty()

    with st.sidebar:
        st.header("분석 조건")
        with st.form("analysis_form", clear_on_submit=False):
            company_name = st.text_input("기업명", value="삼성전자")
            bsns_year = st.number_input("사업연도", min_value=2015, max_value=2100, value=2024, step=1)
            report_name = st.selectbox("보고서 종류", REPORT_OPTIONS)
            analyze_clicked = st.form_submit_button("분석하기", type="primary", use_container_width=True)

    if analyze_clicked:
        queue_new_analysis(company_name, int(bsns_year), report_name)

    analysis_error_message = st.session_state.pop("analysis_error_message", None)
    pending_analysis_request = st.session_state.get("pending_analysis_request")
    with st.sidebar:
        render_session_history_sidebar()

    if pending_analysis_request:
        st.session_state.pop("pending_analysis_request", None)
        draft_session_id = str(pending_analysis_request.get("draft_session_id") or "")
        try:
            run_analysis_with_progress(
                str(pending_analysis_request["company_name"]),
                int(pending_analysis_request["bsns_year"]),
                str(pending_analysis_request["report_name"]),
                draft_session_id=draft_session_id,
            )
        except Exception as exc:
            cleanup_draft_session(draft_session_id)
            st.session_state["analysis_error_message"] = str(exc)
            st.session_state["scroll_to_top"] = True
            st.rerun()
        return

    body.empty()
    with body.container():
        if analysis_error_message:
            st.error(f"분석을 완료하지 못했습니다. {analysis_error_message}")
            st.caption("기업명을 다시 확인하거나 왼쪽 최근 대화에서 이전 분석으로 돌아갈 수 있습니다.")
        elif "last_analysis" in st.session_state:
            render_analysis_result(st.session_state["last_analysis"])
            render_followup_area()
        else:
            st.caption("왼쪽 사이드바에서 기업명과 보고서 조건을 입력한 뒤 분석하기를 눌러주세요.")


if __name__ == "__main__":
    main()
