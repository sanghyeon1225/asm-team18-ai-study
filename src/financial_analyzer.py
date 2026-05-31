from dataclasses import dataclass
import math

import pandas as pd


KEY_ACCOUNT_CANDIDATES = {
    "revenue": [
        "매출액",
        "수익(매출액)",
        "영업수익",
        "매출",
        "매출수익",
        "상품매출",
        "제품매출",
        "수익",
    ],
    "operating_profit": [
        "영업이익",
        "영업이익(손실)",
        "영업손익",
        "영업손실",
        "영업손익(손실)",
    ],
    "net_income": [
        "당기순이익",
        "당기순이익(손실)",
        "분기순이익",
        "분기순이익(손실)",
        "반기순이익",
        "반기순이익(손실)",
        "연결당기순이익",
        "당기순손익",
        "당기순손실",
    ],
    "assets": [
        "자산총계",
        "총자산",
        "자산 합계",
        "자산총액",
    ],
    "liabilities": [
        "부채총계",
        "총부채",
        "부채 합계",
        "부채총액",
    ],
    "equity": [
        "자본총계",
        "총자본",
        "자본 합계",
        "자본총액",
        "자본합계",
    ],
}

GROWTH_KEYS = {
    "revenue_growth": "revenue",
    "operating_profit_growth": "operating_profit",
    "net_income_growth": "net_income",
    "assets_growth": "assets",
    "liabilities_growth": "liabilities",
    "equity_growth": "equity",
}


@dataclass(frozen=True)
class FinancialStatement:
    revenue: float | None
    operating_profit: float | None
    net_income: float | None
    total_assets: float | None
    total_liabilities: float | None
    total_equity: float | None


@dataclass(frozen=True)
class FinancialRatios:
    operating_margin: float | None
    net_margin: float | None
    roe: float | None
    debt_ratio: float | None
    equity_ratio: float | None


def parse_amount(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    text = str(value).strip()
    if text in {"", "-"}:
        return None

    is_parenthesized_negative = text.startswith("(") and text.endswith(")")
    if is_parenthesized_negative:
        text = text[1:-1].strip()

    text = text.replace(",", "").replace(" ", "")
    if text in {"", "-"}:
        return None

    try:
        amount = int(text)
    except ValueError:
        return None

    return -amount if is_parenthesized_negative else amount


def _preferred_statement_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    if "fs_div" in df.columns:
        fs_div = df["fs_div"].fillna("").astype(str).str.upper().str.strip()
        cfs_rows = df[fs_div == "CFS"]
        if not cfs_rows.empty:
            return cfs_rows

        ofs_rows = df[fs_div == "OFS"]
        if not ofs_rows.empty:
            return ofs_rows

    if "fs_nm" in df.columns:
        fs_nm = df["fs_nm"].fillna("").astype(str)
        cfs_rows = df[fs_nm.str.contains("연결", regex=False, na=False)]
        if not cfs_rows.empty:
            return cfs_rows

    return df


def _first_valid_amount(rows: pd.DataFrame) -> int | None:
    if "thstrm_amount" not in rows.columns:
        return None

    for value in rows["thstrm_amount"]:
        amount = parse_amount(value)
        if amount is not None:
            return amount
    return None


def pick_account(df: pd.DataFrame, candidates: list[str]) -> int | None:
    if df.empty or "account_nm" not in df.columns:
        return None

    scoped_df = _preferred_statement_rows(df)
    account_names = scoped_df["account_nm"].fillna("").astype(str).str.strip()

    for candidate in candidates:
        exact_rows = scoped_df[account_names == candidate]
        amount = _first_valid_amount(exact_rows)
        if amount is not None:
            return amount

    for candidate in candidates:
        contained_rows = scoped_df[account_names.str.contains(candidate, regex=False, na=False)]
        amount = _first_valid_amount(contained_rows)
        if amount is not None:
            return amount

    return None


def extract_key_numbers(df: pd.DataFrame) -> dict[str, int | None]:
    return {
        key: pick_account(df, candidates)
        for key, candidates in KEY_ACCOUNT_CANDIDATES.items()
    }


def safe_divide(numerator: float | int | None, denominator: float | int | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator)


def calculate_ratios(numbers: dict) -> dict[str, float | None]:
    return {
        "operating_margin": safe_divide(numbers.get("operating_profit"), numbers.get("revenue")),
        "net_margin": safe_divide(numbers.get("net_income"), numbers.get("revenue")),
        "roe": safe_divide(numbers.get("net_income"), numbers.get("equity")),
        "debt_ratio": safe_divide(numbers.get("liabilities"), numbers.get("equity")),
        "equity_ratio": safe_divide(numbers.get("equity"), numbers.get("assets")),
    }


def calculate_growth(current_numbers: dict, previous_numbers: dict) -> dict[str, float | None]:
    growth = {}
    for growth_key, number_key in GROWTH_KEYS.items():
        current_value = current_numbers.get(number_key)
        previous_value = previous_numbers.get(number_key)
        if current_value is None or previous_value is None or previous_value <= 0:
            growth[growth_key] = None
            continue
        if number_key in {"operating_profit", "net_income"} and current_value <= 0:
            growth[growth_key] = None
            continue
        growth[growth_key] = (float(current_value) - float(previous_value)) / abs(float(previous_value))
    return growth


def format_ratio(value: float | None) -> str:
    if value is None:
        return "데이터 없음"
    return f"{value * 100:.2f}%"


def detect_risk_signals(numbers: dict, ratios: dict) -> list[str]:
    signals = []

    revenue = numbers.get("revenue")
    equity = numbers.get("equity")
    debt_ratio = ratios.get("debt_ratio")
    operating_margin = ratios.get("operating_margin")
    net_margin = ratios.get("net_margin")

    if debt_ratio is not None and debt_ratio > 2:
        signals.append("부채비율이 200%를 초과해 재무 안정성 추가 확인 필요")
    if operating_margin is not None and operating_margin < 0:
        signals.append("영업이익률이 음수라 본업 수익성 추가 확인 필요")
    if net_margin is not None and net_margin < 0:
        signals.append("순이익률이 음수라 최종 손익 구조 추가 확인 필요")
    if equity is None or equity <= 0:
        signals.append("자본총계가 없거나 0 이하라 재무구조 추가 확인 필요")
    if revenue is None or revenue == 0:
        signals.append("매출액 데이터가 없거나 0이라 실적 규모 추가 확인 필요")

    return signals


def calculate_financial_ratios(statement: FinancialStatement) -> FinancialRatios:
    return FinancialRatios(
        operating_margin=safe_divide(statement.operating_profit, statement.revenue),
        net_margin=safe_divide(statement.net_income, statement.revenue),
        roe=safe_divide(statement.net_income, statement.total_equity),
        debt_ratio=safe_divide(statement.total_liabilities, statement.total_equity),
        equity_ratio=safe_divide(statement.total_equity, statement.total_assets),
    )
