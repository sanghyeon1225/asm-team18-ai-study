import pytest

from src import dart_client
from src.dart_client import CORP_CODE_COLUMNS, DartApiError, DartClientError, REPORT_CODES


SAMPLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<result>
    <list>
        <corp_code>00126380</corp_code>
        <corp_name>삼성전자</corp_name>
        <corp_eng_name>SAMSUNG ELECTRONICS CO., LTD.</corp_eng_name>
        <stock_code>005930</stock_code>
        <modify_date>20240101</modify_date>
    </list>
    <list>
        <corp_code>00164779</corp_code>
        <corp_name>삼성물산</corp_name>
        <corp_eng_name>SAMSUNG C&amp;T CORPORATION</corp_eng_name>
        <stock_code></stock_code>
        <modify_date>20240102</modify_date>
    </list>
</result>
"""


def test_parse_corp_code_xml_returns_expected_dataframe() -> None:
    result = dart_client.parse_corp_code_xml(SAMPLE_XML)

    assert list(result.columns) == CORP_CODE_COLUMNS
    assert len(result) == 2
    assert result.iloc[0]["corp_code"] == "00126380"
    assert result.iloc[0]["stock_code"] == "005930"
    assert result.iloc[1]["stock_code"] == ""


def test_parse_corp_code_xml_raises_for_dart_error() -> None:
    error_xml = """
    <result>
        <status>010</status>
        <message>등록되지 않은 키입니다.</message>
    </result>
    """

    with pytest.raises(DartClientError, match="OpenDART 오류\\(010\\)"):
        dart_client.parse_corp_code_xml(error_xml)


def test_find_corp_candidates_prefers_listed_company(tmp_path) -> None:
    cache_path = tmp_path / "corp_codes.csv"
    dart_client.parse_corp_code_xml(SAMPLE_XML).to_csv(cache_path, index=False)

    candidates = dart_client.find_corp_candidates("삼성", cache_path=cache_path)

    assert candidates.iloc[0]["corp_name"] == "삼성전자"
    assert candidates.iloc[0]["stock_code"] == "005930"


def test_find_best_corp_code_returns_exact_match(tmp_path) -> None:
    cache_path = tmp_path / "corp_codes.csv"
    dart_client.parse_corp_code_xml(SAMPLE_XML).to_csv(cache_path, index=False)

    assert dart_client.find_best_corp_code("삼성물산", cache_path=cache_path) == "00164779"


class MockResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_get_single_company_accounts_returns_dataframe(monkeypatch) -> None:
    captured = {}

    def fake_get(url: str, params: dict, timeout: int) -> MockResponse:
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return MockResponse(
            {
                "status": "000",
                "message": "정상",
                "list": [
                    {
                        "corp_code": "00126380",
                        "bsns_year": "2024",
                        "account_nm": "매출액",
                        "thstrm_amount": "1000",
                    }
                ],
            }
        )

    monkeypatch.setenv("DART_API_KEY", "test-dart-key")
    monkeypatch.setattr(dart_client.requests, "get", fake_get)

    result = dart_client.get_single_company_accounts("00126380", 2024, REPORT_CODES["사업보고서"])

    assert captured["url"] == dart_client.DART_SINGLE_COMPANY_ACCOUNTS_URL
    assert captured["params"] == {
        "crtfc_key": "test-dart-key",
        "corp_code": "00126380",
        "bsns_year": "2024",
        "reprt_code": "11011",
    }
    assert captured["timeout"] == 30
    assert result.iloc[0]["account_nm"] == "매출액"


def test_get_single_company_accounts_raises_for_dart_status_013(monkeypatch) -> None:
    def fake_get(url: str, params: dict, timeout: int) -> MockResponse:
        return MockResponse({"status": "013", "message": "조회된 데이터가 없습니다."})

    monkeypatch.setenv("DART_API_KEY", "test-dart-key")
    monkeypatch.setattr(dart_client.requests, "get", fake_get)

    with pytest.raises(DartApiError, match="OpenDART 오류\\(013\\)"):
        dart_client.get_single_company_accounts("00126380", 2024)
