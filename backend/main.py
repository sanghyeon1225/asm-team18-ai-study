from __future__ import annotations

from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from backend.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    ChatRequest,
    ChatResponse,
    SessionListResponse,
    SessionResponse,
    SuggestRequest,
    SuggestResponse,
)
from backend.session_store import add_message, create_session, get_messages, get_session, list_sessions
from src.llm_client import answer_followup_question, suggest_company_names
from src.workflow import build_financial_workflow


load_dotenv()

app = FastAPI(
    title="공시톡 FastAPI Backend",
    description="OpenDART 재무제표 분석 workflow와 추가 질문 챗봇 API",
    version="0.2.0",
)

RAW_ACCOUNT_COLUMNS = ["fs_div", "fs_nm", "sj_div", "account_nm", "thstrm_amount"]


def _raw_accounts_preview(accounts: Any, limit: int = 30) -> list[dict[str, Any]]:
    if not isinstance(accounts, pd.DataFrame) or accounts.empty:
        return []

    columns = [column for column in RAW_ACCOUNT_COLUMNS if column in accounts.columns]
    preview = accounts.loc[:, columns] if columns else accounts
    return preview.head(limit).fillna("").astype(str).to_dict("records")


def _records_from_state(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, pd.DataFrame):
        return value.fillna("").astype(str).to_dict("records")
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    return []


def _build_analysis_context(state: dict[str, Any]) -> dict[str, Any]:
    selected = state.get("selected_company") or {}
    current_df = state.get("current_df")
    previous_numbers = state.get("previous_numbers")
    year = int(state.get("year") or 0)

    candidate_companies = _records_from_state(state.get("candidate_companies"))
    if not candidate_companies and selected:
        candidate_companies = [selected]

    return {
        "company_name": str(selected.get("corp_name") or state.get("company_name") or ""),
        "year": year,
        "previous_year": year - 1,
        "report_code": str(state.get("report_code") or ""),
        "report_name": str(state.get("report_name") or ""),
        "selected_company": selected,
        "candidate_companies": candidate_companies,
        "numbers": state.get("numbers") or {},
        "previous_numbers": previous_numbers,
        "previous_data_available": previous_numbers is not None,
        "ratios": state.get("ratios") or {},
        "growth": state.get("growth") or {},
        "risk_signals": state.get("risk_signals") or [],
        "raw_accounts": _raw_accounts_preview(current_df),
        "explanation": state.get("explanation") or "",
    }


def _followup_context(context: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = [
        "company_name",
        "year",
        "report_name",
        "numbers",
        "ratios",
        "previous_year",
        "previous_numbers",
        "previous_data_available",
        "growth",
        "risk_signals",
        "raw_accounts",
    ]
    return {key: context.get(key) for key in allowed_keys}


def run_analysis(request: AnalysisRequest) -> dict[str, Any]:
    workflow = build_financial_workflow()
    state = workflow.invoke(
        {
            "company_name": request.company_name.strip(),
            "year": int(request.year),
            "report_code": request.report_code,
            "report_name": request.report_name,
            "error": None,
        }
    )

    if state.get("error"):
        raise ValueError(str(state["error"]))

    return _build_analysis_context(state)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analysis", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    try:
        context = run_analysis(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"분석 처리 중 예상하지 못한 오류가 발생했습니다. 입력값과 API 설정을 확인해주세요. 상세: {exc}",
        ) from exc

    session_id = create_session(context)
    return {
        **context,
        "session_id": session_id,
        "messages": [],
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict[str, Any]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="질문을 입력해주세요.")

    session_id = request.session_id
    if session_id:
        session = get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다. 분석을 다시 실행해주세요.")
        context = session["analysis"]
    elif request.context:
        context = request.context
        session_id = create_session(context)
    else:
        raise HTTPException(status_code=400, detail="분석 컨텍스트가 없습니다. 먼저 분석을 실행해주세요.")

    try:
        answer = answer_followup_question(_followup_context(context), question)
        add_message(session_id, "user", question)
        add_message(session_id, "assistant", answer)
        messages = get_messages(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"추가 질문 답변 생성에 실패했습니다. 상세: {exc}") from exc

    return {
        "session_id": session_id,
        "answer": answer,
        "messages": messages,
    }


@app.post("/suggest", response_model=SuggestResponse)
def suggest(request: SuggestRequest) -> dict[str, Any]:
    try:
        suggestions = suggest_company_names(request.company_name.strip())
    except Exception:
        suggestions = []
    return {"suggestions": suggestions}


@app.get("/sessions", response_model=SessionListResponse)
def get_chat_sessions() -> dict[str, Any]:
    return {"sessions": list_sessions()}


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_chat_session(session_id: str) -> dict[str, Any]:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
    return {
        "session_id": session_id,
        "analysis": session["analysis"],
        "messages": session["messages"],
        "title": session.get("title", ""),
        "created_at": session.get("created_at", ""),
        "updated_at": session.get("updated_at", ""),
    }
