from __future__ import annotations

from typing import Any

import pandas as pd
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from src.dart_client import find_corp_candidates, get_single_company_accounts
from src.financial_analyzer import (
    calculate_growth,
    calculate_ratios,
    detect_risk_signals,
    extract_key_numbers,
    format_ratio,
)
from src.llm_client import decide_additional_analysis, generate_financial_explanation
from src.safety import SAFETY_DISCLAIMER, sanitize_financial_answer


class FinancialWorkflowState(TypedDict, total=False):
    company_name: str
    year: int
    report_code: str
    report_name: str
    corp_code: str
    selected_company: dict[str, Any]
    candidate_companies: list[dict[str, Any]]
    current_df: pd.DataFrame | None
    previous_df: pd.DataFrame | None
    numbers: dict[str, int | None]
    previous_numbers: dict[str, int | None] | None
    ratios: dict[str, float | None]
    growth: dict[str, float | None]
    risk_signals: list[str]
    agent_decision: dict[str, Any]
    additional_analysis: dict[str, Any]
    explanation: str
    error: str | None


INVESTMENT_DISCLAIMER = SAFETY_DISCLAIMER


def _error(message: str) -> FinancialWorkflowState:
    return {"error": message}


def _has_error(state: FinancialWorkflowState) -> bool:
    return bool(state.get("error"))


def resolve_company_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    try:
        candidates = find_corp_candidates(state.get("company_name", ""))
        if candidates.empty:
            return _error(f"'{state.get('company_name', '')}'에 해당하는 기업 후보를 찾지 못했습니다.")

        selected_company = candidates.iloc[0].fillna("").astype(str).to_dict()
        candidate_companies = candidates.head(10).fillna("").astype(str).to_dict("records")
        return {
            "corp_code": str(selected_company["corp_code"]),
            "selected_company": selected_company,
            "candidate_companies": candidate_companies,
            "error": None,
        }
    except Exception as exc:
        return _error(f"기업 고유번호 조회에 실패했습니다. {exc}")


def fetch_current_financials_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    try:
        current_df = get_single_company_accounts(
            str(state["corp_code"]),
            int(state["year"]),
            str(state["report_code"]),
        )
        return {"current_df": current_df}
    except Exception as exc:
        return _error(f"현재 연도 재무제표 조회에 실패했습니다. {exc}")


def fetch_previous_financials_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    try:
        previous_df = get_single_company_accounts(
            str(state["corp_code"]),
            int(state["year"]) - 1,
            str(state["report_code"]),
        )
        return {"previous_df": previous_df}
    except Exception:
        return {"previous_df": None, "previous_numbers": None, "growth": {}}


def analyze_financials_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    current_df = state.get("current_df")
    if current_df is None or current_df.empty:
        return _error("현재 연도 재무제표 데이터가 비어 있습니다.")

    numbers = extract_key_numbers(current_df)
    ratios = calculate_ratios(numbers)
    risk_signals = detect_risk_signals(numbers, ratios)

    previous_numbers = None
    previous_df = state.get("previous_df")
    if previous_df is not None and not previous_df.empty:
        extracted_previous = extract_key_numbers(previous_df)
        if any(value is not None for value in extracted_previous.values()):
            previous_numbers = extracted_previous

    growth = calculate_growth(numbers, previous_numbers) if previous_numbers else {}

    return {
        "numbers": numbers,
        "previous_numbers": previous_numbers,
        "ratios": ratios,
        "growth": growth,
        "risk_signals": risk_signals,
    }


def _format_amount(value: int | float | None) -> str:
    if value is None:
        return "데이터 없음"
    return f"{float(value):,.0f}원"


def _section(title: str, summary: str, items: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "summary": summary,
        "items": items,
    }


def decide_additional_analysis_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    decision = decide_additional_analysis(
        numbers=state.get("numbers", {}),
        ratios=state.get("ratios", {}),
        growth=state.get("growth", {}),
        risk_signals=state.get("risk_signals", []),
    )
    return {"agent_decision": decision}


def run_additional_analysis_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    decision = state.get("agent_decision") or {}
    if not decision.get("needs_additional_analysis"):
        return {"additional_analysis": {}}

    numbers = state.get("numbers", {})
    ratios = state.get("ratios", {})
    growth = state.get("growth", {})
    analysis_types = decision.get("analysis_types") or []
    additional_analysis: dict[str, Any] = {}

    if "debt_risk" in analysis_types:
        additional_analysis["debt_risk"] = _section(
            "부채 안정성 추가 분석",
            "부채와 자본의 균형을 추가로 확인했습니다.",
            [
                f"부채비율: {format_ratio(ratios.get('debt_ratio'))}",
                f"자기자본비율: {format_ratio(ratios.get('equity_ratio'))}",
                f"부채총계: {_format_amount(numbers.get('liabilities'))}",
                f"자본총계: {_format_amount(numbers.get('equity'))}",
            ],
        )

    if "profitability" in analysis_types:
        additional_analysis["profitability"] = _section(
            "수익성 추가 분석",
            "영업이익과 순이익 흐름을 추가로 확인했습니다.",
            [
                f"영업이익률: {format_ratio(ratios.get('operating_margin'))}",
                f"순이익률: {format_ratio(ratios.get('net_margin'))}",
                f"영업이익: {_format_amount(numbers.get('operating_profit'))}",
                f"당기순이익: {_format_amount(numbers.get('net_income'))}",
            ],
        )

    if "growth" in analysis_types:
        additional_analysis["growth"] = _section(
            "성장성 추가 분석",
            "전년도 대비 변동 폭이 큰 항목을 추가로 확인했습니다.",
            [
                f"매출 성장률: {format_ratio(growth.get('revenue_growth'))}",
                f"영업이익 성장률: {format_ratio(growth.get('operating_profit_growth'))}",
                f"순이익 성장률: {format_ratio(growth.get('net_income_growth'))}",
                f"자산 성장률: {format_ratio(growth.get('assets_growth'))}",
            ],
        )

    if "capital_structure" in analysis_types:
        additional_analysis["capital_structure"] = _section(
            "자본 구조 추가 분석",
            "자산, 부채, 자본의 구성 비율을 추가로 확인했습니다.",
            [
                f"자산총계: {_format_amount(numbers.get('assets'))}",
                f"부채총계: {_format_amount(numbers.get('liabilities'))}",
                f"자본총계: {_format_amount(numbers.get('equity'))}",
                f"자기자본비율: {format_ratio(ratios.get('equity_ratio'))}",
            ],
        )

    if "raw_account_review" in analysis_types:
        missing_keys = [key for key, value in numbers.items() if value is None]
        missing_text = ", ".join(missing_keys) if missing_keys else "추가 누락 항목 없음"
        additional_analysis["raw_account_review"] = _section(
            "원본 계정 확인 필요",
            "일부 계정은 기업별 표기 차이 때문에 원본 공시 계정 확인이 도움이 됩니다.",
            [
                f"추출되지 않은 핵심 계정: {missing_text}",
                "DART 주요계정 원본과 사업보고서 주석을 함께 확인하는 것이 좋습니다.",
            ],
        )

    return {"additional_analysis": additional_analysis}


def generate_explanation_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    try:
        selected_company = state.get("selected_company", {})
        company_name = str(selected_company.get("corp_name") or state.get("company_name", ""))
        explanation = generate_financial_explanation(
            company_name=company_name,
            year=int(state["year"]),
            report_name=str(state["report_name"]),
            numbers=state.get("numbers", {}),
            ratios=state.get("ratios", {}),
            risk_signals=state.get("risk_signals", []),
            growth=state.get("growth") if state.get("previous_numbers") else None,
        )
        return {"explanation": explanation}
    except Exception as exc:
        return {"explanation": f"AI 해설을 생성하지 못했습니다. {exc}"}


def validate_answer_node(state: FinancialWorkflowState) -> FinancialWorkflowState:
    if _has_error(state):
        return {}

    explanation = state.get("explanation", "")
    if not explanation:
        return {}

    return {"explanation": sanitize_financial_answer(explanation)}


def build_financial_workflow():
    graph = StateGraph(FinancialWorkflowState)
    graph.add_node("resolve_company", resolve_company_node)
    graph.add_node("fetch_current_financials", fetch_current_financials_node)
    graph.add_node("fetch_previous_financials", fetch_previous_financials_node)
    graph.add_node("analyze_financials", analyze_financials_node)
    graph.add_node("decide_additional_analysis", decide_additional_analysis_node)
    graph.add_node("run_additional_analysis", run_additional_analysis_node)
    graph.add_node("generate_explanation", generate_explanation_node)
    graph.add_node("validate_answer", validate_answer_node)

    graph.add_edge(START, "resolve_company")
    graph.add_edge("resolve_company", "fetch_current_financials")
    graph.add_edge("fetch_current_financials", "fetch_previous_financials")
    graph.add_edge("fetch_previous_financials", "analyze_financials")
    graph.add_edge("analyze_financials", "decide_additional_analysis")
    graph.add_edge("decide_additional_analysis", "run_additional_analysis")
    graph.add_edge("run_additional_analysis", "generate_explanation")
    graph.add_edge("generate_explanation", "validate_answer")
    graph.add_edge("validate_answer", END)

    return graph.compile()
