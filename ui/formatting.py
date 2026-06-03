"""금액·비율 포맷팅과 표·차트 데이터 빌더 (표현 계층 헬퍼)."""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.financial_analyzer import format_ratio
from src.safety import SAFETY_DISCLAIMER
from ui.config import GROWTH_LABELS, NUMBER_LABELS, RATIO_LABELS


def format_amount_eok(value: int | float | None) -> str:
    if value is None:
        return "데이터 없음"
    return f"{float(value) / 100_000_000:,.2f}억 원"


def amount_to_eok(value: int | float | None) -> float | None:
    if value is None:
        return None
    return float(value) / 100_000_000


def build_numbers_table(numbers: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "항목": label,
                "금액": format_amount_eok(numbers.get(key)),
            }
            for key, label in NUMBER_LABELS.items()
        ]
    )


def build_ratios_table(ratios: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "항목": label,
                "비율": format_ratio(ratios.get(key)),
            }
            for key, label in RATIO_LABELS.items()
        ]
    )


def build_numbers_chart_data(numbers: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "항목": label,
            "금액(억 원)": amount_to_eok(numbers.get(key)),
        }
        for key, label in NUMBER_LABELS.items()
    ]
    chart_data = pd.DataFrame(rows).set_index("항목")
    chart_data["금액(억 원)"] = pd.to_numeric(chart_data["금액(억 원)"], errors="coerce")
    return chart_data


def build_comparison_chart_data(
    current_numbers: dict[str, Any],
    previous_numbers: dict[str, Any],
    current_year: int,
    previous_year: int,
) -> pd.DataFrame:
    rows = []
    for key, label in NUMBER_LABELS.items():
        rows.append(
            {
                "항목": label,
                f"{current_year}년": amount_to_eok(current_numbers.get(key)),
                f"{previous_year}년": amount_to_eok(previous_numbers.get(key)),
            }
        )
    chart_data = pd.DataFrame(rows).set_index("항목")
    chart_data[f"{current_year}년"] = pd.to_numeric(chart_data[f"{current_year}년"], errors="coerce")
    chart_data[f"{previous_year}년"] = pd.to_numeric(chart_data[f"{previous_year}년"], errors="coerce")
    return chart_data


def format_growth(value: float | None, previous_data_available: bool) -> str:
    if not previous_data_available:
        return "전년도 비교 데이터 없음"
    if value is None:
        return "추가 확인 필요"
    return format_ratio(value)


def build_growth_table(
    current_numbers: dict[str, Any],
    previous_numbers: dict[str, Any] | None,
    growth: dict[str, Any],
    previous_data_available: bool,
) -> pd.DataFrame:
    rows = []
    for growth_key, (number_key, label) in GROWTH_LABELS.items():
        rows.append(
            {
                "항목": label,
                "현재 연도": format_amount_eok(current_numbers.get(number_key)),
                "전년도": (
                    format_amount_eok(previous_numbers.get(number_key))
                    if previous_data_available and previous_numbers is not None
                    else "전년도 비교 데이터 없음"
                ),
                "전년 대비": format_growth(growth.get(growth_key), previous_data_available),
            }
        )
    return pd.DataFrame(rows)


def strip_disclaimer_from_explanation(explanation: str) -> str:
    if not explanation:
        return ""

    lines: list[str] = []
    for line in explanation.splitlines():
        stripped = line.strip()
        if SAFETY_DISCLAIMER in stripped:
            while lines and not lines[-1].strip():
                lines.pop()
            if lines:
                previous = lines[-1].strip().lstrip("#").strip()
                if "면책" in previous:
                    lines.pop()
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def truncate_text(value: str, limit: int = 30) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."
