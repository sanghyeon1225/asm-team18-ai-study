import pandas as pd

from src.financial_analyzer import (
    FinancialStatement,
    calculate_growth,
    calculate_ratios,
    calculate_financial_ratios,
    detect_risk_signals,
    extract_key_numbers,
    format_ratio,
    parse_amount,
    safe_divide,
)


def test_parse_amount() -> None:
    assert parse_amount("1,234,567") == 1234567
    assert parse_amount("-") is None
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount("(1,234)") == -1234


def test_safe_divide_returns_none_for_zero_denominator() -> None:
    assert safe_divide(10, 0) is None


def test_calculate_ratios() -> None:
    numbers = {
        "revenue": 1000,
        "operating_profit": 120,
        "net_income": 80,
        "assets": 2000,
        "liabilities": 800,
        "equity": 1200,
    }

    ratios = calculate_ratios(numbers)

    assert ratios["operating_margin"] == 0.12
    assert ratios["net_margin"] == 0.08
    assert ratios["roe"] == 80 / 1200
    assert ratios["debt_ratio"] == 800 / 1200
    assert ratios["equity_ratio"] == 0.6


def test_calculate_growth() -> None:
    current_numbers = {
        "revenue": 1200,
        "operating_profit": 150,
        "net_income": 90,
        "assets": 2200,
        "liabilities": 900,
        "equity": 1300,
    }
    previous_numbers = {
        "revenue": 1000,
        "operating_profit": 100,
        "net_income": 60,
        "assets": 2000,
        "liabilities": 800,
        "equity": 1200,
    }

    growth = calculate_growth(current_numbers, previous_numbers)

    assert growth["revenue_growth"] == 0.2
    assert growth["operating_profit_growth"] == 0.5
    assert growth["net_income_growth"] == 0.5
    assert growth["assets_growth"] == 0.1
    assert growth["liabilities_growth"] == 0.125
    assert growth["equity_growth"] == 100 / 1200


def test_calculate_growth_returns_none_for_missing_or_ambiguous_values() -> None:
    current_numbers = {
        "revenue": 1200,
        "operating_profit": -20,
        "net_income": 30,
        "assets": 2200,
        "liabilities": 900,
        "equity": 1300,
    }
    previous_numbers = {
        "revenue": 0,
        "operating_profit": 100,
        "net_income": -10,
        "assets": None,
        "liabilities": 800,
        "equity": 1200,
    }

    growth = calculate_growth(current_numbers, previous_numbers)

    assert growth["revenue_growth"] is None
    assert growth["operating_profit_growth"] is None
    assert growth["net_income_growth"] is None
    assert growth["assets_growth"] is None
    assert growth["liabilities_growth"] == 0.125
    assert growth["equity_growth"] == 100 / 1200


def test_format_ratio() -> None:
    assert format_ratio(None) == "데이터 없음"
    assert format_ratio(0.1234) == "12.34%"


def test_detect_risk_signals_uses_non_decisive_wording() -> None:
    numbers = {
        "revenue": 0,
        "operating_profit": -10,
        "net_income": -20,
        "assets": 100,
        "liabilities": 300,
        "equity": 100,
    }
    ratios = {
        "debt_ratio": 3.0,
        "operating_margin": -0.1,
        "net_margin": -0.2,
    }

    signals = detect_risk_signals(numbers, ratios)

    assert len(signals) == 4
    assert all("추가 확인 필요" in signal for signal in signals)
    assert not any("매수" in signal or "매도" in signal or "투자" in signal for signal in signals)


def test_detect_risk_signals_flags_missing_or_non_positive_equity() -> None:
    numbers = {
        "revenue": 1000,
        "operating_profit": 100,
        "net_income": 50,
        "assets": 1000,
        "liabilities": 1200,
        "equity": 0,
    }
    ratios = calculate_ratios(numbers)

    signals = detect_risk_signals(numbers, ratios)

    assert signals == ["자본총계가 없거나 0 이하라 재무구조 추가 확인 필요"]


def test_calculate_financial_ratios() -> None:
    statement = FinancialStatement(
        revenue=1000,
        operating_profit=100,
        net_income=80,
        total_assets=2000,
        total_liabilities=800,
        total_equity=1200,
    )

    ratios = calculate_financial_ratios(statement)

    assert ratios.operating_margin == 0.1
    assert ratios.net_margin == 0.08
    assert ratios.roe == 80 / 1200
    assert ratios.debt_ratio == 800 / 1200
    assert ratios.equity_ratio == 0.6


def test_extract_key_numbers_prefers_cfs_and_handles_account_variants() -> None:
    df = pd.DataFrame(
        [
            {"fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "900"},
            {"fs_div": "CFS", "account_nm": "수익(매출액)", "thstrm_amount": "1,000"},
            {"fs_div": "CFS", "account_nm": "영업이익(손실)", "thstrm_amount": "(200)"},
            {"fs_div": "CFS", "account_nm": "당기순이익(손실)", "thstrm_amount": "150"},
            {"fs_div": "CFS", "account_nm": "자산총계", "thstrm_amount": "5,000"},
            {"fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "2,000"},
            {"fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "3,000"},
        ]
    )

    result = extract_key_numbers(df)

    assert result == {
        "revenue": 1000,
        "operating_profit": -200,
        "net_income": 150,
        "assets": 5000,
        "liabilities": 2000,
        "equity": 3000,
    }


def test_extract_key_numbers_uses_ofs_when_cfs_is_missing() -> None:
    df = pd.DataFrame(
        [
            {"fs_div": "OFS", "account_nm": "매출액", "thstrm_amount": "1,500"},
            {"fs_div": "OFS", "account_nm": "영업이익", "thstrm_amount": "200"},
            {"fs_div": "OFS", "account_nm": "당기순이익", "thstrm_amount": "100"},
            {"fs_div": "OFS", "account_nm": "자산총계", "thstrm_amount": "4,000"},
            {"fs_div": "OFS", "account_nm": "부채총계", "thstrm_amount": "1,000"},
            {"fs_div": "OFS", "account_nm": "자본총계", "thstrm_amount": "3,000"},
        ]
    )

    result = extract_key_numbers(df)

    assert result["revenue"] == 1500
    assert result["operating_profit"] == 200
    assert result["equity"] == 3000
