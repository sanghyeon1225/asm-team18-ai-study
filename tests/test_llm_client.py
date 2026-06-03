from src import llm_client
from src.safety import SAFETY_DISCLAIMER


class FakeMessage:
    content = "1. 한 줄 요약\n테스트 해설입니다."


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def create(self, **kwargs) -> FakeResponse:
        FakeOpenAI.calls.append(kwargs)
        return FakeResponse()


class FakeChat:
    completions = FakeCompletions()


class FakeOpenAI:
    calls = []
    api_key = None
    base_url = None

    def __init__(self, api_key: str, base_url: str) -> None:
        FakeOpenAI.api_key = api_key
        FakeOpenAI.base_url = base_url
        self.chat = FakeChat()


def test_generate_financial_explanation_returns_fallback_without_api_key(monkeypatch) -> None:
    class FailingOpenAI:
        def __init__(self, api_key: str, base_url: str) -> None:
            raise AssertionError("Upstage client should not be called without an API key.")

    monkeypatch.setenv("UPSTAGE_API_KEY", "")
    monkeypatch.setattr(llm_client, "OpenAI", FailingOpenAI)

    result = llm_client.generate_financial_explanation(
        company_name="테스트전자",
        year=2024,
        report_name="사업보고서",
        numbers={},
        ratios={},
        risk_signals=[],
    )

    assert "UPSTAGE_API_KEY" in result
    assert "LLM 호출을 수행하지 않았습니다" in result


def test_generate_financial_explanation_calls_upstage_with_policy_prompt(monkeypatch) -> None:
    FakeOpenAI.calls = []
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setenv("UPSTAGE_BASE_URL", "https://api.upstage.ai/v1")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-test")
    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)

    result = llm_client.generate_financial_explanation(
        company_name="테스트전자",
        year=2024,
        report_name="사업보고서",
        numbers={"revenue": 1000, "operating_profit": 100},
        ratios={"operating_margin": 0.1},
        growth={"revenue_growth": 0.2},
        risk_signals=["부채비율 추가 확인 필요"],
    )

    assert result == f"1. 한 줄 요약\n테스트 해설입니다.\n\n{SAFETY_DISCLAIMER}"
    assert FakeOpenAI.api_key == "test-upstage-key"
    assert FakeOpenAI.base_url == "https://api.upstage.ai/v1"
    assert FakeOpenAI.calls[0]["model"] == "solar-test"
    assert FakeOpenAI.calls[0]["reasoning_effort"] == "high"
    assert FakeOpenAI.calls[0]["stream"] is False
    assert FakeOpenAI.calls[0]["temperature"] == 0.2

    messages = FakeOpenAI.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "투자 추천" in messages[0]["content"]
    assert "매수/매도" in messages[0]["content"]
    assert "목표주가" in messages[0]["content"]
    assert "제공된 숫자와 계산 결과만 사용한다" in messages[0]["content"]
    assert "전년 대비 증가를 무조건 긍정적으로 해석하지 않는다" in messages[0]["content"]

    user_prompt = messages[1]["content"]
    assert "테스트전자" in user_prompt
    assert '"revenue": 1000' in user_prompt
    assert '"formatted": "10.00%"' in user_prompt
    assert '"revenue_growth":' in user_prompt
    assert '"formatted": "20.00%"' in user_prompt
    assert "1. 한 줄 요약" in user_prompt
    assert "6. 면책 문구" in user_prompt


def test_decide_additional_analysis_returns_rule_fallback_without_api_key(monkeypatch) -> None:
    class FailingOpenAI:
        def __init__(self, api_key: str, base_url: str) -> None:
            raise AssertionError("Upstage client should not be called without an API key.")

    monkeypatch.setenv("UPSTAGE_API_KEY", "")
    monkeypatch.setattr(llm_client, "OpenAI", FailingOpenAI)

    result = llm_client.decide_additional_analysis(
        numbers={"revenue": 1000, "liabilities": 3000, "equity": 1000},
        ratios={"debt_ratio": 3.0, "equity_ratio": 0.25},
        growth={},
        risk_signals=["부채비율이 200%를 초과해 재무 안정성 추가 확인 필요"],
    )

    assert result["needs_additional_analysis"] is True
    assert result["analysis_types"] == ["debt_risk", "capital_structure"]
    assert result["source"] == "rule_fallback"


def test_decide_additional_analysis_calls_upstage_with_json_prompt(monkeypatch) -> None:
    class FakeDecisionMessage:
        content = '{"needs_additional_analysis": true, "analysis_types": ["growth", "unknown"], "reason": "성장률 변동이 큽니다."}'

    class FakeDecisionChoice:
        message = FakeDecisionMessage()

    class FakeDecisionResponse:
        choices = [FakeDecisionChoice()]

    class FakeDecisionCompletions:
        def create(self, **kwargs) -> FakeDecisionResponse:
            FakeDecisionOpenAI.calls.append(kwargs)
            return FakeDecisionResponse()

    class FakeDecisionChat:
        completions = FakeDecisionCompletions()

    class FakeDecisionOpenAI:
        calls = []

        def __init__(self, api_key: str, base_url: str) -> None:
            self.chat = FakeDecisionChat()

    FakeDecisionOpenAI.calls = []
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-test")
    monkeypatch.setattr(llm_client, "OpenAI", FakeDecisionOpenAI)

    result = llm_client.decide_additional_analysis(
        numbers={"revenue": 1000},
        ratios={"operating_margin": 0.1},
        growth={"revenue_growth": 0.4},
        risk_signals=[],
    )

    assert result == {
        "needs_additional_analysis": True,
        "analysis_types": ["growth"],
        "reason": "성장률 변동이 큽니다.",
        "source": "llm",
    }
    assert FakeDecisionOpenAI.calls[0]["model"] == "solar-test"
    assert FakeDecisionOpenAI.calls[0]["temperature"] == 0
    assert "추가 분석 라우터" in FakeDecisionOpenAI.calls[0]["messages"][0]["content"]
    assert '"revenue_growth":' in FakeDecisionOpenAI.calls[0]["messages"][1]["content"]


def test_answer_followup_question_returns_fallback_without_api_key(monkeypatch) -> None:
    class FailingOpenAI:
        def __init__(self, api_key: str, base_url: str) -> None:
            raise AssertionError("Upstage client should not be called without an API key.")

    monkeypatch.setenv("UPSTAGE_API_KEY", "")
    monkeypatch.setattr(llm_client, "OpenAI", FailingOpenAI)

    result = llm_client.answer_followup_question({"company_name": "테스트전자"}, "부채가 많아?")

    assert "UPSTAGE_API_KEY" in result
    assert "LLM 호출을 수행하지 않았습니다" in result


def test_answer_followup_question_calls_upstage_with_saved_context(monkeypatch) -> None:
    FakeOpenAI.calls = []
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setenv("UPSTAGE_MODEL", "solar-test")
    monkeypatch.setattr(llm_client, "OpenAI", FakeOpenAI)

    result = llm_client.answer_followup_question(
        {
            "company_name": "테스트전자",
            "numbers": {"liabilities": 300, "equity": 100},
            "ratios": {"debt_ratio": 3.0},
            "risk_signals": ["부채비율이 200%를 초과해 재무 안정성 추가 확인 필요"],
        },
        "부채가 많은 편이야?",
    )

    assert result == f"1. 한 줄 요약\n테스트 해설입니다.\n\n{SAFETY_DISCLAIMER}"
    assert FakeOpenAI.calls[0]["model"] == "solar-test"
    assert FakeOpenAI.calls[0]["reasoning_effort"] == "high"
    assert FakeOpenAI.calls[0]["stream"] is False

    messages = FakeOpenAI.calls[0]["messages"]
    assert messages[0]["role"] == "system"
    assert "저장된 재무 데이터 안에서만 답한다" in messages[0]["content"]
    assert "투자 추천" in messages[0]["content"]
    assert "재무정보 해설 관점으로 우회" in messages[0]["content"]

    user_prompt = messages[1]["content"]
    assert "테스트전자" in user_prompt
    assert '"debt_ratio": 3.0' in user_prompt
    assert "부채가 많은 편이야?" in user_prompt


def test_answer_followup_question_redirects_investment_advice_without_llm(monkeypatch) -> None:
    class FailingOpenAI:
        def __init__(self, api_key: str, base_url: str) -> None:
            raise AssertionError("Upstage client should not be called for investment advice requests.")

    monkeypatch.setenv("UPSTAGE_API_KEY", "test-upstage-key")
    monkeypatch.setattr(llm_client, "OpenAI", FailingOpenAI)

    result = llm_client.answer_followup_question({"company_name": "테스트전자"}, "삼성전자 사도 돼?")

    assert "매수/매도 판단은 제공할 수 없습니다" in result
    assert "수익성, 안정성, 성장성" in result
    assert SAFETY_DISCLAIMER in result
