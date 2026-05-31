from __future__ import annotations

import re


SAFETY_DISCLAIMER = "본 서비스는 투자 추천이 아닌 공시 기반 재무정보 해설 도구입니다."

INVESTMENT_ADVICE_PATTERNS = [
    r"매수",
    r"매도",
    r"사도\s*돼",
    r"사도\s*될",
    r"사야",
    r"팔아야",
    r"팔까",
    r"목표\s*주가",
    r"목표주가",
    r"수익률",
    r"추천",
    r"종목\s*추천",
    r"투자\s*해도",
    r"투자\s*할까",
    r"오를까",
    r"내릴까",
]

UNSAFE_SENTENCE_PATTERNS = [
    r".*(매수|매도)\s*(추천|의견|해야|하는 것이 좋|하세요|해도 됩니다).*",
    r".*(사야|팔아야)\s*(합니다|해요|한다).*",
    r".*사도\s*(됩니다|돼요|돼).*",
    r".*팔아도\s*(됩니다|돼요|돼).*",
    r".*목표\s*주가.*",
    r".*수익률\s*(예상|예측|전망).*",
    r".*종목.*추천.*",
]


def detect_investment_advice_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return any(re.search(pattern, normalized) for pattern in INVESTMENT_ADVICE_PATTERNS)


def investment_advice_redirect_answer() -> str:
    return (
        "매수/매도 판단은 제공할 수 없습니다. "
        "대신 공시 기준으로 수익성, 안정성, 성장성을 확인할 수 있습니다. "
        "예를 들어 영업이익률과 순이익률은 돈을 벌어들이는 힘을, 부채비율과 자기자본비율은 재무 안정성을, "
        "전년 대비 매출액과 이익 변화는 성장성 흐름을 보는 데 도움이 됩니다.\n\n"
        f"{SAFETY_DISCLAIMER}"
    )


def _is_unsafe_sentence(sentence: str) -> bool:
    stripped = sentence.strip()
    if not stripped:
        return False
    return any(re.search(pattern, stripped) for pattern in UNSAFE_SENTENCE_PATTERNS)


def sanitize_financial_answer(answer: str) -> str:
    if not answer:
        return SAFETY_DISCLAIMER

    lines = []
    for line in answer.splitlines():
        if _is_unsafe_sentence(line):
            lines.append("해당 내용은 투자 판단으로 오해될 수 있어 공시 기반 재무정보 해설 관점으로만 확인이 필요합니다.")
        else:
            lines.append(line)

    sanitized = "\n".join(lines).strip()
    if SAFETY_DISCLAIMER not in sanitized:
        sanitized = f"{sanitized}\n\n{SAFETY_DISCLAIMER}".strip()
    return sanitized
