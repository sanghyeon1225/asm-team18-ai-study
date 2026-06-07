from __future__ import annotations

import time
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

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
from src.logging_config import configure_logging, get_logger
from src.llm_client import answer_followup_question, suggest_company_names
from src.workflow import build_financial_workflow


load_dotenv()
configure_logging("backend")
logger = get_logger(__name__)

app = FastAPI(
    title="공시톡 FastAPI Backend",
    description="OpenDART 재무제표 분석 workflow와 추가 질문 챗봇 API",
    version="0.2.0",
)

RAW_ACCOUNT_COLUMNS = ["fs_div", "fs_nm", "sj_div", "account_nm", "thstrm_amount"]


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started_at = time.perf_counter()
    logger.debug("HTTP 요청 시작 | %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception("HTTP 요청 실패 | %s %s | %sms", request.method, request.url.path, elapsed_ms)
        raise

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    if response.status_code >= 400:
        logger.warning(
            "HTTP 응답 오류 | %s %s | 상태=%s | %sms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    else:
        logger.debug("HTTP 요청 완료 | %s %s | 상태=%s | %sms", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


def _preview_text(value: str, limit: int = 80) -> str:
    text = " ".join((value or "").split())
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


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
        "agent_decision": state.get("agent_decision") or {},
        "additional_analysis": state.get("additional_analysis") or {},
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
        "agent_decision",
        "additional_analysis",
        "raw_accounts",
    ]
    return {key: context.get(key) for key in allowed_keys}


def run_analysis(request: AnalysisRequest) -> dict[str, Any]:
    company_name = request.company_name.strip()
    logger.debug(
        "분석 워크플로우 시작 | 기업=%s | 연도=%s | 보고서=%s",
        company_name,
        request.year,
        request.report_name,
    )
    workflow = build_financial_workflow()
    state = workflow.invoke(
        {
            "company_name": company_name,
            "year": int(request.year),
            "report_code": request.report_code,
            "report_name": request.report_name,
            "error": None,
        }
    )

    if state.get("error"):
        logger.warning("분석 워크플로우 중단 | 기업=%s | 원인=%s", company_name, state["error"])
        raise ValueError(str(state["error"]))

    context = _build_analysis_context(state)
    logger.info(
        "분석 워크플로우 완료 | 기업=%s | 위험신호=%s개 | 추가분석=%s개 | 원본미리보기=%s행",
        context.get("company_name"),
        len(context.get("risk_signals") or []),
        len(context.get("additional_analysis") or {}),
        len(context.get("raw_accounts") or []),
    )
    return context


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analysis", response_model=AnalysisResponse)
def analyze(request: AnalysisRequest) -> dict[str, Any]:
    logger.info(
        "분석 요청 접수 | 기업=%s | 연도=%s | 보고서코드=%s",
        request.company_name.strip(),
        request.year,
        request.report_code,
    )
    try:
        context = run_analysis(request)
    except ValueError as exc:
        logger.warning("분석 요청 거절 | 기업=%s | 원인=%s", request.company_name.strip(), exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("분석 요청 처리 실패 | 기업=%s", request.company_name.strip())
        raise HTTPException(
            status_code=500,
            detail="분석 처리 중 오류가 발생했습니다. 입력값과 API 설정을 확인한 뒤 다시 시도해주세요.",
        ) from exc

    session_id = create_session(context)
    logger.info(
        "분석 세션 생성 | 세션=%s | 기업=%s | 연도=%s",
        session_id,
        context.get("company_name"),
        context.get("year"),
    )
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
    logger.info(
        "추가 질문 접수 | 세션=%s | 질문=%s",
        session_id or "new-from-context",
        _preview_text(question),
    )
    if session_id:
        session = get_session(session_id)
        if session is None:
            logger.warning("추가 질문 세션 없음 | 세션=%s", session_id)
            raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다. 분석을 다시 실행해주세요.")
        context = session["analysis"]
    elif request.context:
        context = request.context
        session_id = create_session(context)
        logger.info("추가 질문용 세션 생성 | 세션=%s", session_id)
    else:
        logger.warning("추가 질문 거절 | 분석 컨텍스트 없음")
        raise HTTPException(status_code=400, detail="분석 컨텍스트가 없습니다. 먼저 분석을 실행해주세요.")

    try:
        answer = answer_followup_question(_followup_context(context), question)
        add_message(session_id, "user", question)
        add_message(session_id, "assistant", answer)
        messages = get_messages(session_id)
    except Exception as exc:
        logger.exception("추가 질문 답변 생성 실패 | 세션=%s", session_id)
        raise HTTPException(status_code=500, detail="추가 질문 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.") from exc

    logger.info("추가 질문 답변 완료 | 세션=%s | 누적메시지=%s개", session_id, len(messages))
    return {
        "session_id": session_id,
        "answer": answer,
        "messages": messages,
    }


@app.post("/suggest", response_model=SuggestResponse)
def suggest(request: SuggestRequest) -> dict[str, Any]:
    logger.debug("기업명 후보 요청 | 입력=%s", _preview_text(request.company_name))
    try:
        suggestions = suggest_company_names(request.company_name.strip())
    except Exception:
        logger.exception("기업명 후보 생성 실패 | 입력=%s", _preview_text(request.company_name))
        suggestions = []
    logger.debug("기업명 후보 완료 | 개수=%s개", len(suggestions))
    return {"suggestions": suggestions}


@app.get("/sessions", response_model=SessionListResponse)
def get_chat_sessions() -> dict[str, Any]:
    sessions = list_sessions()
    logger.debug("세션 목록 조회 | 개수=%s개", len(sessions))
    return {"sessions": sessions}


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_chat_session(session_id: str) -> dict[str, Any]:
    logger.debug("세션 상세 조회 | 세션=%s", session_id)
    session = get_session(session_id)
    if session is None:
        logger.warning("세션 상세 없음 | 세션=%s", session_id)
        raise HTTPException(status_code=404, detail="채팅 세션을 찾을 수 없습니다.")
    logger.debug(
        "세션 상세 반환 | 세션=%s | 메시지=%s개",
        session_id,
        len(session.get("messages") or []),
    )
    return {
        "session_id": session_id,
        "analysis": session["analysis"],
        "messages": session["messages"],
        "title": session.get("title", ""),
        "created_at": session.get("created_at", ""),
        "updated_at": session.get("updated_at", ""),
    }
