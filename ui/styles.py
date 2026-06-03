"""채팅·대시보드 커스텀 CSS 주입.

실제 CSS 규칙은 같은 디렉터리의 styles.css에 두고, 여기서는 그 파일을 읽어
<style>로 감싸 한 번에 주입한다. CSS와 Python을 분리해 양쪽 모두 다루기 쉽게 했다.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st


_STYLES_CSS_PATH = Path(__file__).with_name("styles.css")


def render_chat_styles() -> None:
    css = _STYLES_CSS_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)
