import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from src.financial_analyzer import format_ratio
from src.safety import (
    detect_investment_advice_request,
    investment_advice_redirect_answer,
    sanitize_financial_answer,
)


DEFAULT_UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"
DEFAULT_UPSTAGE_MODEL = "solar-pro3"
DEFAULT_REASONING_EFFORT = "high"

SYSTEM_PROMPT = """너는 공시 기반 재무제표 해설 도우미다.
투자 추천, 매수/매도 의견, 목표주가, 수익률 예측을 절대 하지 않는다.
제공된 숫자와 계산 결과만 사용한다.
숫자가 없는 항목은 추측하지 않는다.
전년 대비 증가를 무조건 긍정적으로 해석하지 않는다.
손실 축소, 이익 전환, 손실 확대처럼 해석이 애매한 항목은 추가 확인 필요라고 설명한다.
초보자도 이해할 수 있게 설명한다."""

FOLLOWUP_SYSTEM_PROMPT = """너는 공시 기반 재무제표 추가 질문 답변 도우미다.
저장된 재무 데이터 안에서만 답한다.
모르는 것은 모른다고 답한다.
투자 추천, 매수/매도 판단, 목표주가, 수익률 예측은 하지 않는다.
질문이 투자 추천이면 재무정보 해설 관점으로 우회한다.
초보자도 이해할 수 있게 짧고 명확하게 답한다."""


def get_upstage_api_key() -> str | None:
    load_dotenv()
    return os.getenv("UPSTAGE_API_KEY", "").strip() or None


def get_upstage_base_url() -> str:
    load_dotenv()
    return os.getenv("UPSTAGE_BASE_URL", DEFAULT_UPSTAGE_BASE_URL).strip() or DEFAULT_UPSTAGE_BASE_URL


def get_upstage_model() -> str:
    load_dotenv()
    return os.getenv("UPSTAGE_MODEL", DEFAULT_UPSTAGE_MODEL).strip() or DEFAULT_UPSTAGE_MODEL


def create_upstage_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=get_upstage_base_url())


def fallback_financial_explanation(company_name: str) -> str:
    return (
        f"{company_name} 재무제표 해설을 생성하려면 UPSTAGE_API_KEY가 필요합니다.\n\n"
        "프로젝트 루트의 .env 파일에 UPSTAGE_API_KEY=발급받은_키 형식으로 추가한 뒤 다시 실행해주세요. "
        "API 키가 없어 현재는 LLM 호출을 수행하지 않았습니다."
    )


def fallback_followup_answer() -> str:
    return (
        "추가 질문에 답하려면 UPSTAGE_API_KEY가 필요합니다. "
        "현재는 LLM 호출을 수행하지 않았습니다."
    )


def _format_payload(numbers: dict, ratios: dict, risk_signals: list[str], growth: dict | None = None) -> str:
    ratio_payload = {
        key: {
            "raw": value,
            "formatted": format_ratio(value),
        }
        for key, value in ratios.items()
    }
    payload = {
        "numbers": numbers,
        "ratios": ratio_payload,
        "growth": {
            key: {
                "raw": value,
                "formatted": format_ratio(value),
            }
            for key, value in (growth or {}).items()
        },
        "risk_signals": risk_signals,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _format_followup_context(context: dict) -> str:
    return json.dumps(context, ensure_ascii=False, indent=2, default=str)


def _build_user_prompt(
    company_name: str,
    year: int,
    report_name: str,
    numbers: dict,
    ratios: dict,
    risk_signals: list[str],
    growth: dict | None = None,
) -> str:
    return f"""아래 제공 데이터만 사용해 재무제표 해설을 작성해줘.

회사명: {company_name}
사업연도: {year}
보고서: {report_name}

제공 데이터:
{_format_payload(numbers, ratios, risk_signals, growth)}

반드시 아래 형식을 지켜줘.
1. 한 줄 요약
2. 수익성 분석
3. 안정성 분석
4. 주의해야 할 신호
5. 추가로 확인하면 좋은 항목
6. 면책 문구

면책 문구에는 이 설명이 공시 기반 교육용 해설이며 투자 판단이나 매수/매도 권유가 아니라는 점을 포함해줘."""


def generate_financial_explanation(
    company_name: str,
    year: int,
    report_name: str,
    numbers: dict,
    ratios: dict,
    risk_signals: list[str],
    growth: dict | None = None,
) -> str:
    api_key = get_upstage_api_key()
    if not api_key:
        return fallback_financial_explanation(company_name)

    client = create_upstage_client(api_key)
    response = client.chat.completions.create(
        model=get_upstage_model(),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _build_user_prompt(company_name, year, report_name, numbers, ratios, risk_signals, growth),
            },
        ],
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        stream=False,
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if not content:
        return "AI 해설 결과가 비어 있습니다. 입력 데이터와 API 응답 상태를 확인해주세요."

    return sanitize_financial_answer(content.strip())


COMPANY_SUGGESTION_SYSTEM_PROMPT = """너는 한국 기업명 교정 도우미다.
사용자가 입력한 기업명에 오타가 있거나 정확하지 않을 때, 실제 존재할 가능성이 높은 한국 기업명을 최대 5개 제안한다.
기업명만 쉼표로 구분해서 한 줄로 답한다. 다른 설명은 절대 하지 않는다."""


def suggest_company_names(company_name: str) -> list[str]:
    api_key = get_upstage_api_key()
    if not api_key:
        return []

    client = create_upstage_client(api_key)
    response = client.chat.completions.create(
        model=get_upstage_model(),
        messages=[
            {"role": "system", "content": COMPANY_SUGGESTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"입력: {company_name}"},
        ],
        stream=False,
        temperature=0.1,
    )

    content = response.choices[0].message.content
    if not content:
        return []
    return [name.strip() for name in content.split(",") if name.strip()]


def answer_followup_question(context: dict, question: str) -> str:
    cleaned_question = question.strip()
    if not cleaned_question:
        return "질문을 입력해주세요."
    if detect_investment_advice_request(cleaned_question):
        return investment_advice_redirect_answer()

    api_key = get_upstage_api_key()
    if not api_key:
        return fallback_followup_answer()

    client = create_upstage_client(api_key)
    response = client.chat.completions.create(
        model=get_upstage_model(),
        messages=[
            {"role": "system", "content": FOLLOWUP_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "아래 저장된 분석 컨텍스트 안에서만 질문에 답해줘.\n\n"
                    f"저장된 분석 컨텍스트:\n{_format_followup_context(context)}\n\n"
                    f"사용자 질문: {cleaned_question}"
                ),
            },
        ],
        reasoning_effort=DEFAULT_REASONING_EFFORT,
        stream=False,
        temperature=0.2,
    )

    content = response.choices[0].message.content
    if not content:
        return "추가 질문 답변이 비어 있습니다. 질문을 조금 더 구체적으로 입력해주세요."

    return sanitize_financial_answer(content.strip())
