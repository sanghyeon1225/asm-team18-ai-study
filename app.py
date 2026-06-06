"""공시톡 Streamlit 프론트엔드 진입점.

UI 로직은 ui/ 패키지의 역할별 모듈에 있고, 여기서는 페이지를 조립한다.
"""
from __future__ import annotations

import streamlit as st

from ui.analysis import (
    queue_new_analysis,
    render_analysis_result,
    run_analysis_with_progress,
)
from ui.api import post_suggest
from ui.chat import render_followup_area
from ui.config import REPORT_OPTIONS
from ui.scroll import render_top_anchor, scroll_to_chat_once, scroll_to_top_once
from ui.session import cleanup_draft_session, render_session_history_sidebar
from ui.styles import render_chat_styles


def _clear_error_and_suggestions() -> None:
    st.session_state.pop("analysis_error_message", None)
    st.session_state.pop("company_suggestions", None)
    st.session_state.pop("company_suggestions_params", None)


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
        _clear_error_and_suggestions()
        queue_new_analysis(company_name, int(bsns_year), report_name)

    # .get() 사용 — 에러 메시지가 세션에 유지돼야 버튼 클릭 시 재렌더링에서도 버튼이 표시됨
    analysis_error_message = st.session_state.get("analysis_error_message")
    pending_analysis_request = st.session_state.get("pending_analysis_request")
    with st.sidebar:
        render_session_history_sidebar()

    if pending_analysis_request:
        st.session_state.pop("pending_analysis_request", None)
        _clear_error_and_suggestions()
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
            error_msg = str(exc)
            st.session_state["analysis_error_message"] = error_msg
            if "기업 후보를 찾지 못했습니다" in error_msg:
                fetched = post_suggest(str(pending_analysis_request["company_name"]))
                if fetched:
                    st.session_state["company_suggestions"] = fetched
                    st.session_state["company_suggestions_params"] = {
                        "bsns_year": int(pending_analysis_request["bsns_year"]),
                        "report_name": str(pending_analysis_request["report_name"]),
                    }
            st.session_state["scroll_to_top"] = True
            st.rerun()
        return

    body.empty()
    with body.container():
        if analysis_error_message:
            st.error(f"분석을 완료하지 못했습니다. {analysis_error_message}")
            suggestions = st.session_state.get("company_suggestions")
            suggestions_params = st.session_state.get("company_suggestions_params", {})
            if suggestions:
                st.write("혹시 이 기업을 찾으셨나요?")
                cols = st.columns(min(len(suggestions), 5))
                for i, name in enumerate(suggestions[:5]):
                    if cols[i].button(name, key=f"suggest_{i}"):
                        _clear_error_and_suggestions()
                        queue_new_analysis(
                            name,
                            int(suggestions_params.get("bsns_year", bsns_year)),
                            str(suggestions_params.get("report_name", report_name)),
                        )
            else:
                st.caption("기업명을 다시 확인하거나 왼쪽 최근 대화에서 이전 분석으로 돌아갈 수 있습니다.")
        elif "last_analysis" in st.session_state:
            render_analysis_result(st.session_state["last_analysis"])
            render_followup_area()
        else:
            st.caption("왼쪽 사이드바에서 기업명과 보고서 조건을 입력한 뒤 분석하기를 눌러주세요.")

    scroll_to_chat_once()


if __name__ == "__main__":
    main()
