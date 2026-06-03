"""페이지 상단 앵커와 강제 스크롤 헬퍼."""
from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components


def render_top_anchor() -> None:
    st.markdown('<div id="gongsitalk-page-top"></div>', unsafe_allow_html=True)


def scroll_to_top_once() -> None:
    if not st.session_state.pop("scroll_to_top", False):
        return
    force_scroll_to_top()


def force_scroll_to_top() -> None:
    components.html(
        """
        <script>
        const scrollTop = () => {
            const parentWindow = window.parent;
            const doc = parentWindow.document;
            const anchor = doc.getElementById("gongsitalk-page-top");
            if (anchor) {
                anchor.scrollIntoView({ block: "start", inline: "nearest", behavior: "auto" });
            }
            try {
                parentWindow.scrollTo({ top: 0, left: 0, behavior: "auto" });
            } catch (error) {}
            const selectors = [
                "html",
                "body",
                "[data-testid='stAppViewContainer']",
                "[data-testid='stMain']",
                "section.main",
                ".main"
            ];
            selectors
                .map((selector) => doc.querySelector(selector))
                .filter(Boolean)
                .forEach((element) => {
                    element.scrollTop = 0;
                    element.scrollLeft = 0;
                });
        };
        [0, 40, 100, 220, 420, 800].forEach((delay) => setTimeout(scrollTop, delay));
        </script>
        """,
        height=0,
    )
