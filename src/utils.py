import os

from dotenv import load_dotenv


def get_required_env(name: str) -> str:
    load_dotenv()
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} 환경변수가 설정되어 있지 않습니다.")
    return value
