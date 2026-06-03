"""환경설정과 화면 표시용 상수."""
from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()

DEFAULT_BACKEND_URL = "http://localhost:8000"
BACKEND_URL = os.getenv("GONGSITALK_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
DRAFT_SESSION_PREFIX = "draft-"

NUMBER_LABELS = {
    "revenue": "매출액",
    "operating_profit": "영업이익",
    "net_income": "당기순이익",
    "assets": "자산총계",
    "liabilities": "부채총계",
    "equity": "자본총계",
}

RATIO_LABELS = {
    "operating_margin": "영업이익률",
    "net_margin": "순이익률",
    "roe": "ROE",
    "debt_ratio": "부채비율",
    "equity_ratio": "자기자본비율",
}

GROWTH_LABELS = {
    "revenue_growth": ("revenue", "매출액 증가율"),
    "operating_profit_growth": ("operating_profit", "영업이익 증가율"),
    "net_income_growth": ("net_income", "당기순이익 증가율"),
    "assets_growth": ("assets", "자산총계 증가율"),
    "liabilities_growth": ("liabilities", "부채총계 증가율"),
    "equity_growth": ("equity", "자본총계 증가율"),
}

REPORT_OPTIONS = ["사업보고서", "반기", "1분기", "3분기"]
