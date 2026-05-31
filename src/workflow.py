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
)
from src.llm_client import generate_financial_explanation
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
    graph.add_node("generate_explanation", generate_explanation_node)
    graph.add_node("validate_answer", validate_answer_node)

    graph.add_edge(START, "resolve_company")
    graph.add_edge("resolve_company", "fetch_current_financials")
    graph.add_edge("fetch_current_financials", "fetch_previous_financials")
    graph.add_edge("fetch_previous_financials", "analyze_financials")
    graph.add_edge("analyze_financials", "generate_explanation")
    graph.add_edge("generate_explanation", "validate_answer")
    graph.add_edge("validate_answer", END)

    return graph.compile()
