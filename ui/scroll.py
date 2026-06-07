"""페이지 상단/채팅 하단 앵커와 강제 스크롤 헬퍼."""
from __future__ import annotations

import urllib.parse

import streamlit as st


def _html_to_data_url(html: str) -> str:
    return "data:text/html;charset=utf-8," + urllib.parse.quote(html)


def _run_html(html: str) -> None:
    st.iframe(_html_to_data_url(html), height=1, width="content")


def render_top_anchor() -> None:
    st.markdown('<div id="gongsitalk-page-top"></div>', unsafe_allow_html=True)


def render_chat_bottom_anchor() -> None:
    st.markdown('<div id="gongsitalk-chat-bottom"></div>', unsafe_allow_html=True)


def scroll_to_top_once() -> None:
    if not st.session_state.pop("scroll_to_top", False):
        return
    _run_html(
        """
        <!doctype html>
        <html>
          <body>
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
          </body>
        </html>
        """
    )


def scroll_to_chat_once() -> None:
    if not st.session_state.pop("scroll_to_chat", False):
        return
    _run_html(
        """
        <!doctype html>
        <html>
          <body>
            <script>
              const scrollToChat = () => {
                  const doc = window.parent.document;
                  const anchor = doc.getElementById("gongsitalk-chat-bottom");
                  if (anchor) {
                      anchor.scrollIntoView({ block: "end", inline: "nearest", behavior: "auto" });
                  }
              };
              [0, 40, 100, 220, 420, 800].forEach((delay) => setTimeout(scrollToChat, delay));
            </script>
          </body>
        </html>
        """
    )
