import pandas as pd

from src import workflow


def sample_current_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "1,000"},
            {"fs_div": "CFS", "account_nm": "영업이익", "thstrm_amount": "100"},
            {"fs_div": "CFS", "account_nm": "당기순이익", "thstrm_amount": "80"},
            {"fs_div": "CFS", "account_nm": "자산총계", "thstrm_amount": "2,000"},
            {"fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "800"},
            {"fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "1,200"},
        ]
    )


def sample_previous_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"fs_div": "CFS", "account_nm": "매출액", "thstrm_amount": "800"},
            {"fs_div": "CFS", "account_nm": "영업이익", "thstrm_amount": "80"},
            {"fs_div": "CFS", "account_nm": "당기순이익", "thstrm_amount": "40"},
            {"fs_div": "CFS", "account_nm": "자산총계", "thstrm_amount": "1,600"},
            {"fs_div": "CFS", "account_nm": "부채총계", "thstrm_amount": "700"},
            {"fs_div": "CFS", "account_nm": "자본총계", "thstrm_amount": "900"},
        ]
    )


def test_resolve_company_node(monkeypatch) -> None:
    def fake_find_corp_candidates(company_name: str) -> pd.DataFrame:
        assert company_name == "테스트전자"
        return pd.DataFrame(
            [
                {
                    "corp_code": "00123456",
                    "corp_name": "테스트전자",
                    "corp_eng_name": "TEST",
                    "stock_code": "123456",
                    "modify_date": "20240101",
                }
            ]
        )

    monkeypatch.setattr(workflow, "find_corp_candidates", fake_find_corp_candidates)

    result = workflow.resolve_company_node({"company_name": "테스트전자"})

    assert result["corp_code"] == "00123456"
    assert result["selected_company"]["corp_name"] == "테스트전자"
    assert result["error"] is None


def test_fetch_previous_financials_node_does_not_fail_workflow(monkeypatch) -> None:
    def fake_get_single_company_accounts(corp_code: str, year: int, report_code: str) -> pd.DataFrame:
        raise RuntimeError("DART temporary error")

    monkeypatch.setattr(workflow, "get_single_company_accounts", fake_get_single_company_accounts)

    result = workflow.fetch_previous_financials_node(
        {"corp_code": "00123456", "year": 2024, "report_code": "11011"}
    )

    assert result == {"previous_df": None, "previous_numbers": None, "growth": {}}


def test_analyze_financials_node_extracts_numbers_and_growth() -> None:
    result = workflow.analyze_financials_node(
        {
            "current_df": sample_current_df(),
            "previous_df": sample_previous_df(),
        }
    )

    assert result["numbers"]["revenue"] == 1000
    assert result["previous_numbers"]["revenue"] == 800
    assert result["ratios"]["operating_margin"] == 0.1
    assert result["growth"]["revenue_growth"] == 0.25
    assert result["risk_signals"] == []


def test_validate_answer_node_removes_recommendation_and_adds_disclaimer() -> None:
    result = workflow.validate_answer_node(
        {
            "explanation": "수익성은 안정적입니다.\n매수 추천입니다.\n원문 공시도 함께 확인하세요.",
        }
    )

    assert "매수 추천입니다" not in result["explanation"]
    assert "투자 판단으로 오해될 수 있어" in result["explanation"]
    assert "수익성은 안정적입니다." in result["explanation"]
    assert workflow.INVESTMENT_DISCLAIMER in result["explanation"]


def test_build_financial_workflow_invokes_nodes(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow,
        "resolve_company_node",
        lambda state: {
            "corp_code": "00123456",
            "selected_company": {"corp_code": "00123456", "corp_name": "테스트전자"},
            "error": None,
        },
    )
    monkeypatch.setattr(workflow, "fetch_current_financials_node", lambda state: {"current_df": sample_current_df()})
    monkeypatch.setattr(workflow, "fetch_previous_financials_node", lambda state: {"previous_df": sample_previous_df()})
    monkeypatch.setattr(workflow, "generate_explanation_node", lambda state: {"explanation": "테스트 해설"})

    compiled = workflow.build_financial_workflow()
    result = compiled.invoke(
        {
            "company_name": "테스트전자",
            "year": 2024,
            "report_code": "11011",
            "report_name": "사업보고서",
            "error": None,
        }
    )

    assert result["corp_code"] == "00123456"
    assert result["numbers"]["revenue"] == 1000
    assert workflow.INVESTMENT_DISCLAIMER in result["explanation"]
