from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import zipfile
from xml.etree import ElementTree

import pandas as pd
import requests
from dotenv import load_dotenv
from requests import RequestException

from src.logging_config import get_logger


DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
DART_SINGLE_COMPANY_ACCOUNTS_URL = "https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"
DEFAULT_CACHE_PATH = Path("data") / "corp_codes.csv"
CORP_CODE_COLUMNS = ["corp_code", "corp_name", "corp_eng_name", "stock_code", "modify_date"]
REPORT_CODES = {
    "1분기": "11013",
    "반기": "11012",
    "3분기": "11014",
    "사업보고서": "11011",
}

logger = get_logger(__name__)


class DartClientError(RuntimeError):
    """Raised when OpenDART corporation code lookup fails."""


class DartApiError(DartClientError):
    """Raised when OpenDART returns a non-success status."""

    def __init__(self, status: str, message: str = "") -> None:
        self.status = status
        self.message = message or "알 수 없는 오류"
        super().__init__(f"OpenDART 오류({self.status}): {self.message}")


class MissingDartApiKeyError(DartClientError):
    """Raised when DART_API_KEY is not configured."""


def get_dart_api_key() -> str:
    load_dotenv()
    api_key = os.getenv("DART_API_KEY", "").strip()
    if not api_key:
        raise MissingDartApiKeyError(
            "DART_API_KEY가 설정되어 있지 않습니다. "
            "프로젝트 루트의 .env 파일에 DART_API_KEY=발급받은_키 형식으로 추가해주세요."
        )
    return api_key


def _clean_text(value: str | None) -> str:
    return (value or "").strip()


def _read_cached_csv(cache_path: Path) -> pd.DataFrame:
    return _ensure_columns(pd.read_csv(cache_path, dtype=str, keep_default_na=False))


def _ensure_columns(corp_codes: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in CORP_CODE_COLUMNS if column not in corp_codes.columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise DartClientError(f"기업 고유번호 캐시 파일 형식이 올바르지 않습니다. 누락된 컬럼: {missing}")
    return corp_codes.loc[:, CORP_CODE_COLUMNS].fillna("")


def _dart_error_message(xml_content: bytes | str) -> str | None:
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError:
        return None

    status = _clean_text(root.findtext("status"))
    message = _clean_text(root.findtext("message"))
    if status or message:
        return f"OpenDART 오류({status or 'unknown'}): {message or '알 수 없는 오류'}"
    return None


def parse_corp_code_xml(xml_content: bytes | str) -> pd.DataFrame:
    try:
        root = ElementTree.fromstring(xml_content)
    except ElementTree.ParseError as exc:
        raise DartClientError("OpenDART 고유번호 XML 파싱에 실패했습니다.") from exc

    status = _clean_text(root.findtext("status"))
    message = _clean_text(root.findtext("message"))
    if status and status != "000":
        raise DartApiError(status, message)

    rows = []
    for item in root.findall(".//list"):
        rows.append({column: _clean_text(item.findtext(column)) for column in CORP_CODE_COLUMNS})

    return _ensure_columns(pd.DataFrame(rows, columns=CORP_CODE_COLUMNS))


def parse_corp_code_zip(zip_binary: bytes) -> pd.DataFrame:
    try:
        with zipfile.ZipFile(BytesIO(zip_binary)) as archive:
            xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            if not xml_names:
                raise DartClientError("OpenDART 고유번호 ZIP 안에서 XML 파일을 찾지 못했습니다.")

            with archive.open(xml_names[0]) as xml_file:
                return parse_corp_code_xml(xml_file.read())
    except zipfile.BadZipFile as exc:
        error_message = _dart_error_message(zip_binary)
        if error_message:
            raise DartClientError(error_message) from exc
        raise DartClientError("OpenDART 고유번호 응답이 ZIP 형식이 아닙니다.") from exc


def download_corp_codes(api_key: str | None = None, timeout: int = 30) -> pd.DataFrame:
    resolved_api_key = (api_key or "").strip() or get_dart_api_key()

    logger.debug("DART 기업 고유번호 다운로드 시작")
    try:
        response = requests.get(
            DART_CORP_CODE_URL,
            params={"crtfc_key": resolved_api_key},
            timeout=timeout,
        )
        response.raise_for_status()
    except RequestException as exc:
        logger.warning("DART 기업 고유번호 다운로드 실패 | 원인=%s", exc)
        raise DartClientError("OpenDART 고유번호 API 호출에 실패했습니다. 네트워크 상태와 API 키를 확인해주세요.") from exc

    corp_codes = parse_corp_code_zip(response.content)
    logger.info("DART 기업 고유번호 다운로드 완료 | 행=%s개", len(corp_codes))
    return corp_codes


def get_single_company_accounts(
    corp_code: str,
    bsns_year: int | str,
    reprt_code: str = REPORT_CODES["사업보고서"],
) -> pd.DataFrame:
    api_key = get_dart_api_key()
    params = {
        "crtfc_key": api_key,
        "corp_code": str(corp_code).strip(),
        "bsns_year": str(bsns_year).strip(),
        "reprt_code": str(reprt_code).strip(),
    }

    logger.debug(
        "DART 주요계정 조회 시작 | 고유번호=%s | 연도=%s | 보고서=%s",
        params["corp_code"],
        params["bsns_year"],
        params["reprt_code"],
    )
    try:
        response = requests.get(DART_SINGLE_COMPANY_ACCOUNTS_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
    except RequestException as exc:
        logger.warning(
            "DART 주요계정 조회 실패 | 고유번호=%s | 연도=%s | 원인=%s",
            params["corp_code"],
            params["bsns_year"],
            exc,
        )
        raise DartClientError("OpenDART 단일회사 주요계정 API 호출에 실패했습니다.") from exc
    except ValueError as exc:
        logger.warning(
            "DART 주요계정 응답 해석 실패 | 고유번호=%s | 연도=%s",
            params["corp_code"],
            params["bsns_year"],
        )
        raise DartClientError("OpenDART 단일회사 주요계정 JSON 파싱에 실패했습니다.") from exc

    status = _clean_text(payload.get("status"))
    message = _clean_text(payload.get("message"))
    if status != "000":
        logger.warning(
            "DART 주요계정 응답 오류 | 고유번호=%s | 연도=%s | 상태=%s | 메시지=%s",
            params["corp_code"],
            params["bsns_year"],
            status or "unknown",
            message,
        )
        raise DartApiError(status or "unknown", message)

    accounts = pd.DataFrame(payload.get("list") or [])
    if accounts.empty:
        logger.warning(
            "DART 주요계정 데이터 없음 | 고유번호=%s | 연도=%s",
            params["corp_code"],
            params["bsns_year"],
        )
        raise ValueError("OpenDART 단일회사 주요계정 데이터가 비어 있습니다.")

    logger.info(
        "DART 주요계정 조회 완료 | 고유번호=%s | 연도=%s | 행=%s개",
        params["corp_code"],
        params["bsns_year"],
        len(accounts),
    )
    return accounts


def load_corp_codes(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    *,
    force_refresh: bool = False,
    api_key: str | None = None,
) -> pd.DataFrame:
    path = Path(cache_path)
    if path.exists() and not force_refresh:
        logger.debug("DART 기업 고유번호 캐시 사용 | 경로=%s", path)
        return _read_cached_csv(path)

    logger.info("DART 기업 고유번호 캐시 갱신 | 경로=%s | 강제=%s", path, force_refresh)
    corp_codes = download_corp_codes(api_key=api_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    corp_codes.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info("DART 기업 고유번호 캐시 저장 | 경로=%s | 행=%s개", path, len(corp_codes))
    return corp_codes


def find_corp_candidates(
    company_name: str,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    *,
    api_key: str | None = None,
) -> pd.DataFrame:
    query = company_name.strip()
    if not query:
        raise ValueError("기업명을 입력해주세요.")

    logger.debug("DART 기업 후보 검색 시작 | 검색어=%s", query)
    corp_codes = load_corp_codes(cache_path=cache_path, api_key=api_key)
    name_matches = corp_codes["corp_name"].str.contains(query, case=False, regex=False, na=False)
    candidates = corp_codes.loc[name_matches, CORP_CODE_COLUMNS].copy()

    if candidates.empty:
        logger.info("DART 기업 후보 검색 완료 | 검색어=%s | 결과=0개", query)
        return candidates

    candidates["_has_stock_code"] = candidates["stock_code"].str.strip().ne("")
    candidates = candidates.sort_values("_has_stock_code", ascending=False, kind="mergesort")
    result = candidates.drop(columns=["_has_stock_code"]).reset_index(drop=True)
    logger.info("DART 기업 후보 검색 완료 | 검색어=%s | 결과=%s개", query, len(result))
    return result


def find_best_corp_code(
    company_name: str,
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    *,
    api_key: str | None = None,
) -> str:
    candidates = find_corp_candidates(company_name, cache_path=cache_path, api_key=api_key)
    if candidates.empty:
        raise ValueError(f"'{company_name}'에 해당하는 기업을 찾지 못했습니다.")

    query = company_name.strip()
    exact_matches = candidates[candidates["corp_name"].str.strip() == query]
    if not exact_matches.empty:
        return str(exact_matches.iloc[0]["corp_code"])

    return str(candidates.iloc[0]["corp_code"])
