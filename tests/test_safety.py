from src.safety import (
    SAFETY_DISCLAIMER,
    detect_investment_advice_request,
    investment_advice_redirect_answer,
    sanitize_financial_answer,
)


def test_detect_investment_advice_request() -> None:
    assert detect_investment_advice_request("삼성전자 사도 돼?")
    assert detect_investment_advice_request("목표주가랑 수익률 알려줘")
    assert detect_investment_advice_request("종목 추천해줘")
    assert detect_investment_advice_request("이 회사 부채가 많은 편이야?") is False


def test_sanitize_financial_answer_softens_recommendation() -> None:
    result = sanitize_financial_answer("수익성은 양호합니다.\n매수 추천입니다.")

    assert "매수 추천입니다" not in result
    assert "투자 판단으로 오해될 수 있어" in result
    assert SAFETY_DISCLAIMER in result


def test_sanitize_financial_answer_softens_buy_or_sell_wording() -> None:
    result = sanitize_financial_answer("재무비율만 보면 사도 됩니다.\n상황에 따라 팔아도 됩니다.")

    assert "사도 됩니다" not in result
    assert "팔아도 됩니다" not in result
    assert result.count("투자 판단으로 오해될 수 있어") == 2
    assert SAFETY_DISCLAIMER in result


def test_sanitize_financial_answer_adds_disclaimer() -> None:
    result = sanitize_financial_answer("부채비율은 추가 확인이 필요합니다.")

    assert result.endswith(SAFETY_DISCLAIMER)


def test_investment_advice_redirect_answer() -> None:
    result = investment_advice_redirect_answer()

    assert "매수/매도 판단은 제공할 수 없습니다" in result
    assert "수익성, 안정성, 성장성" in result
    assert SAFETY_DISCLAIMER in result
