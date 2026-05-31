from __future__ import annotations

from fastapi.testclient import TestClient

from backend import main as backend_main
from backend.session_store import clear_sessions


def sample_analysis_context() -> dict:
    return {
        "company_name": "테스트전자",
        "year": 2024,
        "previous_year": 2023,
        "report_code": "11011",
        "report_name": "사업보고서",
        "selected_company": {
            "corp_code": "00123456",
            "corp_name": "테스트전자",
            "stock_code": "123456",
        },
        "candidate_companies": [
            {
                "corp_code": "00123456",
                "corp_name": "테스트전자",
                "stock_code": "123456",
            }
        ],
        "numbers": {
            "revenue": 1000,
            "operating_profit": 100,
            "net_income": 80,
            "assets": 2000,
            "liabilities": 800,
            "equity": 1200,
        },
        "previous_numbers": None,
        "previous_data_available": False,
        "ratios": {"operating_margin": 0.1},
        "growth": {},
        "risk_signals": [],
        "raw_accounts": [],
        "explanation": "테스트 해설",
    }


def test_analysis_endpoint_creates_session(monkeypatch) -> None:
    clear_sessions()
    monkeypatch.setattr(backend_main, "run_analysis", lambda request: sample_analysis_context())
    client = TestClient(backend_main.app)

    response = client.post(
        "/analysis",
        json={
            "company_name": "테스트전자",
            "year": 2024,
            "report_code": "11011",
            "report_name": "사업보고서",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"]
    assert payload["company_name"] == "테스트전자"
    assert payload["messages"] == []


def test_chat_endpoint_keeps_message_history(monkeypatch) -> None:
    clear_sessions()
    monkeypatch.setattr(backend_main, "run_analysis", lambda request: sample_analysis_context())
    monkeypatch.setattr(
        backend_main,
        "answer_followup_question",
        lambda context, question: f"저장 데이터 기준 답변: {question}",
    )
    client = TestClient(backend_main.app)

    analysis_response = client.post(
        "/analysis",
        json={
            "company_name": "테스트전자",
            "year": 2024,
            "report_code": "11011",
            "report_name": "사업보고서",
        },
    )
    session_id = analysis_response.json()["session_id"]

    response = client.post(
        "/chat",
        json={
            "session_id": session_id,
            "question": "부채가 많은 편이야?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "저장 데이터 기준 답변: 부채가 많은 편이야?"
    assert payload["messages"] == [
        {"role": "user", "content": "부채가 많은 편이야?"},
        {"role": "assistant", "content": "저장 데이터 기준 답변: 부채가 많은 편이야?"},
    ]


def test_session_list_and_detail_endpoint(monkeypatch) -> None:
    clear_sessions()
    monkeypatch.setattr(backend_main, "run_analysis", lambda request: sample_analysis_context())
    client = TestClient(backend_main.app)

    analysis_response = client.post(
        "/analysis",
        json={
            "company_name": "테스트전자",
            "year": 2024,
            "report_code": "11011",
            "report_name": "사업보고서",
        },
    )
    session_id = analysis_response.json()["session_id"]

    list_response = client.get("/sessions")
    assert list_response.status_code == 200
    sessions = list_response.json()["sessions"]
    assert sessions[0]["session_id"] == session_id
    assert sessions[0]["title"] == "테스트전자 2024 사업보고서"

    detail_response = client.get(f"/sessions/{session_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["session_id"] == session_id
    assert detail["analysis"]["company_name"] == "테스트전자"
    assert detail["messages"] == []


def test_chat_endpoint_requires_analysis_context() -> None:
    clear_sessions()
    client = TestClient(backend_main.app)

    response = client.post("/chat", json={"question": "질문"})

    assert response.status_code == 400
    assert "분석 컨텍스트" in response.json()["detail"]
