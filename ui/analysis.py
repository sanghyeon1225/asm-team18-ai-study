"""분석 실행 흐름과 결과 대시보드 렌더링."""
from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from src.dart_client import REPORT_CODES
from src.logging_config import get_logger
from src.safety import SAFETY_DISCLAIMER
from ui.api import post_json
from ui.formatting import (
    build_comparison_chart_data,
    build_growth_table,
    build_numbers_chart_data,
    build_numbers_table,
    build_ratios_table,
    strip_disclaimer_from_explanation,
)
from ui.session import (
    cache_session,
    cleanup_draft_session,
    clear_current_session,
    create_draft_session,
    upsert_session_summary,
)


logger = get_logger(__name__)


def analysis_context_from_response(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"session_id", "messages"}
    }


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

    logger.info(
        "분석 요청 전송 | 기업=%s | 연도=%s | 보고서=%s | 임시세션=%s",
        company_name,
        bsns_year,
        report_name,
        draft_session_id,
    )
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
    except Exception as exc:
        logger.warning("분석 요청 실패 | 기업=%s | 연도=%s | 보고서=%s | 원인=%s", company_name, bsns_year, report_name, exc)
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
    logger.info(
        "분석 결과 저장 | 세션=%s | 기업=%s | 메시지=%s개",
        result["session_id"],
        analysis.get("company_name"),
        len(messages),
    )
    st.session_state["scroll_to_top"] = True
    st.rerun()


def queue_new_analysis(company_name: str, bsns_year: int, report_name: str) -> None:
    clear_current_session()
    draft_session_id = create_draft_session(company_name, int(bsns_year), report_name)
    logger.info(
        "분석 대기열 등록 | 기업=%s | 연도=%s | 보고서=%s | 임시세션=%s",
        company_name,
        bsns_year,
        report_name,
        draft_session_id,
    )
    st.session_state["pending_analysis_request"] = {
        "company_name": company_name,
        "bsns_year": int(bsns_year),
        "report_name": report_name,
        "draft_session_id": draft_session_id,
    }
    st.session_state["scroll_to_top"] = True
    st.rerun()


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
    st.dataframe(display_candidates.head(10), width="stretch", hide_index=True)


def render_additional_analysis(context: dict[str, Any]) -> None:
    additional_analysis = context.get("additional_analysis") or {}
    if not isinstance(additional_analysis, dict) or not additional_analysis:
        return

    st.subheader("AI 추가 분석")
    decision = context.get("agent_decision") or {}
    reason = str(decision.get("reason") or "").strip() if isinstance(decision, dict) else ""
    if reason:
        st.info(f"추가 분석 판단: {reason}")

    for section in additional_analysis.values():
        if not isinstance(section, dict):
            continue

        title = str(section.get("title") or "추가 분석")
        summary = str(section.get("summary") or "").strip()
        items = section.get("items") or []

        st.markdown(f"**{title}**")
        if summary:
            st.write(summary)
        if items:
            st.markdown("\n".join(f"- {item}" for item in items))


def render_analysis_result(context: dict[str, Any]) -> None:
    logger.debug("분석 결과 렌더링 | 기업=%s | 연도=%s", context.get("company_name"), context.get("year"))
    render_candidate_info(context)

    left, right = st.columns(2)
    with left:
        st.subheader("핵심 재무 수치")
        st.dataframe(build_numbers_table(context["numbers"]), width="stretch", hide_index=True)

    with right:
        st.subheader("재무비율")
        st.dataframe(build_ratios_table(context["ratios"]), width="stretch", hide_index=True)

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
        width="stretch",
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

    render_additional_analysis(context)

    raw_accounts = context.get("raw_accounts") or []
    if raw_accounts:
        with st.expander("DART 주요계정 원본 일부 보기"):
            st.dataframe(pd.DataFrame(raw_accounts), width="stretch", hide_index=True)

    st.subheader("AI 분석 결과")
    explanation = strip_disclaimer_from_explanation(str(context.get("explanation") or ""))
    if explanation:
        st.markdown(explanation)
    st.caption(SAFETY_DISCLAIMER)
