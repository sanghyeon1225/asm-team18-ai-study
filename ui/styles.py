"""채팅·대시보드 커스텀 CSS 주입."""
from __future__ import annotations

import streamlit as st


def render_chat_styles() -> None:
    st.markdown(
        """
        <style>
        .gt-message-spacer {
            height: 0.85rem;
        }
        .gt-user-wrapper,
        .gt-user-wrapper * {
            box-sizing: border-box;
        }
        .gt-user-wrapper {
            display: flex;
            width: 100%;
            justify-content: flex-end;
            height: auto;
            min-height: 0;
        }
        .gt-user-bubble {
            display: inline-block;
            width: fit-content;
            max-width: min(58%, 520px);
            padding: 0.5rem 0.78rem;
            border-radius: 1.12rem;
            background: #2563eb;
            color: #ffffff;
            height: auto;
            min-height: 0;
            line-height: 1.45;
            white-space: pre-wrap;
            overflow-wrap: anywhere;
            font-size: 0.95rem;
            text-align: left;
            box-shadow: none;
        }
        .gt-assistant-avatar {
            box-sizing: border-box;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 2rem;
            height: 2rem;
            margin-top: 0.2rem;
            border-radius: 999px;
            background: #0f172a;
            color: white;
            font-size: 0.78rem;
            font-weight: 800;
            line-height: 1;
        }
        .gt-assistant-body {
            color: #0f172a;
            line-height: 1.65;
        }
        .gt-assistant-name {
            margin-bottom: 0.18rem;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
            line-height: 1.2;
        }
        .gt-thinking-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            width: auto;
            max-width: 100%;
            height: auto;
            min-height: 2rem;
            padding: 0.48rem 0.72rem;
            overflow: hidden;
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 999px;
            background: #f8fafc;
            color: #475569;
            font-size: 0.94rem;
            font-weight: 600;
            line-height: 1.2;
        }
        .gt-typing-dots {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 0.18rem;
            flex: 0 0 auto;
            height: 0.5rem;
            line-height: 1;
        }
        .gt-typing-dot {
            display: block;
            flex: 0 0 0.28rem;
            width: 0.28rem;
            height: 0.28rem;
            margin: 0;
            border-radius: 999px;
            background: #94a3b8;
            animation: gongsitalkPulse 1.25s infinite ease-in-out;
        }
        .gt-typing-dot:nth-child(2) {
            animation-delay: 0.18s;
        }
        .gt-typing-dot:nth-child(3) {
            animation-delay: 0.36s;
        }
        @keyframes gongsitalkPulse {
            0%, 80%, 100% {
                opacity: 0.35;
                transform: translateY(0);
            }
            40% {
                opacity: 1;
                transform: translateY(-1px);
            }
        }
        @media (max-width: 700px) {
            .gt-user-bubble {
                max-width: 86%;
            }
        }
        section[data-testid="stSidebar"] div.stButton > button,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button {
            min-height: 2.28rem;
            padding: 0.44rem 0.62rem;
            border-radius: 0.55rem;
            justify-content: flex-start;
            text-align: left;
            white-space: normal;
            font-size: 0.88rem;
            font-weight: 500;
            line-height: 1.25;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        section[data-testid="stSidebar"] div.stButton > button p,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button p {
            font-size: inherit;
            font-weight: inherit;
            line-height: inherit;
            color: inherit;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:hover {
            border-color: rgba(37, 99, 235, 0.35);
            background: #f8fafc;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled),
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled),
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled),
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled) {
            justify-content: center;
            border-color: #2563eb !important;
            background: #2563eb !important;
            color: #ffffff !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):hover,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):focus,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):hover,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):focus {
            border-color: #1d4ed8 !important;
            background: #1d4ed8 !important;
            color: #ffffff !important;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button[kind="primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled) *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):hover *,
        section[data-testid="stSidebar"] div.stFormSubmitButton button[type="submit"]:not(:disabled):focus *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):hover *,
        section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"]:not(:disabled):focus * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:disabled,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:disabled {
            opacity: 1;
            border-color: rgba(37, 99, 235, 0.26) !important;
            background: #eef2ff !important;
            color: #172554 !important;
            font-weight: 600 !important;
        }
        section[data-testid="stSidebar"] div.stButton > button:disabled *,
        section[data-testid="stSidebar"] div.stFormSubmitButton > button:disabled * {
            color: #172554 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[kind],
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[type="submit"],
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button[data-testid] {
            justify-content: center !important;
            border-color: #2563eb !important;
            background: #2563eb !important;
            background-color: #2563eb !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-weight: 700 !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:focus,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:active {
            border-color: #1d4ed8 !important;
            background: #1d4ed8 !important;
            background-color: #1d4ed8 !important;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:hover *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:focus *,
        section[data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button:active * {
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
        }
        .gt-history-header {
            margin: 0.65rem 0 0.36rem;
            color: #64748b;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
        }
        .gt-analysis-overlay {
            position: static;
            box-sizing: border-box;
            width: 100%;
            max-height: none;
            overflow: visible;
            padding: 0.25rem 0 1rem;
            background: transparent;
            color: #0f172a;
        }
        .gt-analysis-overlay-inner {
            box-sizing: border-box;
            width: min(920px, 100%);
            margin: 0;
            padding: 1rem 1.1rem;
            border: 1px solid rgba(37, 99, 235, 0.18);
            border-radius: 0.9rem;
            background: rgba(255, 255, 255, 0.96);
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.1);
        }
        .gt-analysis-kicker {
            margin: 0 0 0.22rem;
            color: #2563eb;
            font-size: 0.78rem;
            font-weight: 800;
        }
        .gt-analysis-heading {
            margin: 0 0 0.3rem;
            font-size: 1.12rem;
            font-weight: 800;
            line-height: 1.28;
        }
        .gt-analysis-copy {
            margin: 0;
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.45;
        }
        .gt-analysis-steps {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem 0.8rem;
            width: 100%;
            margin-top: 0.75rem;
        }
        .gt-analysis-step {
            display: flex;
            align-items: center;
            gap: 0.42rem;
            min-height: 1.4rem;
            color: #1e293b;
            font-size: 0.82rem;
            line-height: 1.25;
        }
        .gt-analysis-step-dot {
            flex: 0 0 0.46rem;
            width: 0.46rem;
            height: 0.46rem;
            border-radius: 999px;
            background: #2563eb;
            animation: gongsitalkPulse 1.25s infinite ease-in-out;
        }
        @media (max-width: 700px) {
            .gt-analysis-overlay {
                width: 100%;
            }
            .gt-analysis-overlay-inner {
                padding: 0.85rem 0.9rem;
                border-radius: 0.75rem;
            }
            .gt-analysis-steps {
                display: grid;
                gap: 0.4rem;
            }
        }
        .gt-chat-header {
            display: flex;
            align-items: center;
            gap: 0.7rem;
            margin: 0.2rem 0 0.9rem;
            padding: 0.85rem 1rem;
            border: 1px solid rgba(37, 99, 235, 0.16);
            border-radius: 0.9rem;
            background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(14, 165, 233, 0.06));
        }
        .gt-chat-header-icon {
            display: flex;
            align-items: center;
            justify-content: center;
            flex: 0 0 2.5rem;
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 999px;
            background: #2563eb;
            font-size: 1.2rem;
        }
        .gt-chat-header-title {
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 800;
            line-height: 1.3;
        }
        .gt-chat-header-sub {
            margin-top: 0.12rem;
            color: #64748b;
            font-size: 0.82rem;
            line-height: 1.35;
        }
        .gt-welcome-text {
            color: #0f172a;
            line-height: 1.6;
        }
        .gt-chip-label {
            margin: 0.4rem 0 0.5rem;
            color: #475569;
            font-size: 0.84rem;
            font-weight: 700;
        }
        div[class*="st-key-gt-chip-"] button {
            min-height: 0;
            padding: 0.5rem 0.85rem;
            border: 1px solid rgba(37, 99, 235, 0.22);
            border-radius: 999px;
            background: #f8fafc;
            color: #1e293b;
            font-size: 0.88rem;
            font-weight: 500;
            line-height: 1.3;
            text-align: left;
            white-space: normal;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        div[class*="st-key-gt-chip-"] button p {
            font-size: inherit;
            font-weight: inherit;
            color: inherit;
        }
        div[class*="st-key-gt-chip-"] button:hover {
            border-color: #2563eb;
            background: #eff6ff;
            color: #1d4ed8;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
