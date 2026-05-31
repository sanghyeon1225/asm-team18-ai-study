from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    company_name: str = Field(..., min_length=1)
    year: int
    report_code: str = "11011"
    report_name: str = "사업보고서"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AnalysisResponse(BaseModel):
    session_id: str
    company_name: str
    year: int
    previous_year: int
    report_code: str
    report_name: str
    selected_company: dict[str, Any]
    candidate_companies: list[dict[str, Any]]
    numbers: dict[str, int | None]
    previous_numbers: dict[str, int | None] | None
    previous_data_available: bool
    ratios: dict[str, float | None]
    growth: dict[str, float | None]
    risk_signals: list[str]
    raw_accounts: list[dict[str, Any]]
    explanation: str
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    context: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    messages: list[ChatMessage]


class SessionSummary(BaseModel):
    session_id: str
    title: str
    company_name: str | None = None
    year: int | None = None
    report_name: str | None = None
    message_count: int
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionSummary]


class SessionResponse(BaseModel):
    session_id: str
    analysis: dict[str, Any]
    messages: list[ChatMessage]
    title: str
    created_at: str
    updated_at: str
