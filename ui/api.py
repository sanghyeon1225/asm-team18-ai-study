"""FastAPI 백엔드와의 HTTP 통신."""
from __future__ import annotations

from typing import Any

import requests
from requests import RequestException

from ui.config import BACKEND_URL


def api_url(path: str) -> str:
    return f"{BACKEND_URL}{path}"


def post_json(path: str, payload: dict[str, Any], timeout: int = 180) -> dict[str, Any]:
    try:
        response = requests.post(api_url(path), json=payload, timeout=timeout)
    except RequestException as exc:
        raise RuntimeError(
            f"FastAPI 백엔드에 연결할 수 없습니다. 먼저 `uvicorn backend.main:app --reload --port 8000`을 실행해주세요. 상세: {exc}"
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("백엔드 응답을 JSON으로 해석하지 못했습니다.") from exc


def get_json(path: str, timeout: int = 30) -> dict[str, Any]:
    try:
        response = requests.get(api_url(path), timeout=timeout)
    except RequestException as exc:
        raise RuntimeError(
            f"FastAPI 백엔드에 연결할 수 없습니다. 먼저 `uvicorn backend.main:app --reload --port 8000`을 실행해주세요. 상세: {exc}"
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise RuntimeError(str(detail))

    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("백엔드 응답을 JSON으로 해석하지 못했습니다.") from exc
