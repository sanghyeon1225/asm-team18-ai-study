"""FastAPI 백엔드와의 HTTP 통신."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests
from requests import RequestException

from src.logging_config import get_logger
from ui.config import BACKEND_URL


logger = get_logger(__name__)


def api_url(path: str) -> str:
    return f"{BACKEND_URL}{path}"


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _success_log_level(method: str, path: str) -> int:
    if method == "POST" and path in {"/analysis", "/chat"}:
        return logging.INFO
    return logging.DEBUG


def _response_detail(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        detail = response.text
    return str(detail or "").strip()


def _friendly_backend_error(path: str, status_code: int, detail: str) -> str:
    if "기업 후보를 찾지 못했습니다" in detail:
        return "기업 후보를 찾지 못했습니다. 기업명을 다시 확인해주세요."
    if "DART_API_KEY" in detail:
        return "DART API 키가 설정되어 있지 않습니다. `.env` 파일의 `DART_API_KEY`를 확인해주세요."
    if "UPSTAGE_API_KEY" in detail:
        return "Upstage API 키가 없어 AI 답변을 생성하지 못했습니다. `.env` 파일의 `UPSTAGE_API_KEY`를 확인해주세요."
    if "OpenDART" in detail or "DART" in detail:
        return "DART에서 해당 조건의 재무 데이터를 찾지 못했습니다. 기업명, 사업연도, 보고서 종류를 확인해주세요."
    if status_code == 404 and path.startswith("/sessions/"):
        return "이전 대화 세션을 찾지 못했습니다. 새 분석을 다시 실행해주세요."
    if status_code >= 500:
        return "서버 처리 중 문제가 발생했습니다. 입력값과 API 설정을 확인한 뒤 다시 시도해주세요."
    if detail:
        return detail
    return "요청을 처리하지 못했습니다. 입력값을 확인한 뒤 다시 시도해주세요."


def _request_json(method: str, path: str, payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    started_at = time.perf_counter()
    logger.debug("프론트 요청 시작 | %s %s | 백엔드=%s", method, path, BACKEND_URL)

    try:
        if method == "POST":
            response = requests.post(api_url(path), json=payload or {}, timeout=timeout)
        else:
            response = requests.get(api_url(path), timeout=timeout)
    except RequestException as exc:
        logger.warning(
            "백엔드 연결 실패 | %s %s | %sms | 원인=%s",
            method,
            path,
            _elapsed_ms(started_at),
            exc,
        )
        raise RuntimeError("백엔드 서버에 연결할 수 없습니다. 백엔드 실행 후 다시 시도해주세요.") from exc

    elapsed_ms = _elapsed_ms(started_at)
    if response.status_code >= 400:
        detail = _response_detail(response)
        friendly_message = _friendly_backend_error(path, response.status_code, detail)
        logger.warning(
            "프론트 요청 실패 | %s %s | 상태=%s | %sms | 안내=%s | 원인=%s",
            method,
            path,
            response.status_code,
            elapsed_ms,
            friendly_message,
            detail or "-",
        )
        raise RuntimeError(friendly_message)

    try:
        result = response.json()
    except ValueError as exc:
        logger.warning(
            "백엔드 응답 해석 실패 | %s %s | 상태=%s | %sms",
            method,
            path,
            response.status_code,
            elapsed_ms,
        )
        raise RuntimeError("백엔드 응답을 읽지 못했습니다. 잠시 후 다시 시도해주세요.") from exc

    logger.log(
        _success_log_level(method, path),
        "프론트 요청 완료 | %s %s | 상태=%s | %sms",
        method,
        path,
        response.status_code,
        elapsed_ms,
    )
    return result


def post_json(path: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    return _request_json("POST", path, payload, timeout)


def post_suggest(company_name: str) -> list[str]:
    try:
        result = post_json("/suggest", {"company_name": company_name})
        return result.get("suggestions", [])
    except Exception:
        logger.debug("기업명 후보 제안 요청 실패 | 입력=%s", company_name)
        return []


def get_json(path: str, timeout: int = 30) -> dict[str, Any]:
    return _request_json("GET", path, None, timeout)
