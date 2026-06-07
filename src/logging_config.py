from __future__ import annotations

import logging
import os
import sys


DEFAULT_DATE_FORMAT = "%H:%M:%S"
KOREAN_LEVEL_NAMES = {
    logging.DEBUG: "디버그",
    logging.INFO: "정보",
    logging.WARNING: "경고",
    logging.ERROR: "오류",
    logging.CRITICAL: "치명",
}


def _resolve_level() -> int:
    level_name = os.getenv("GONGSITALK_LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, level_name, logging.INFO)


def _apply_korean_level_names() -> None:
    for level, name in KOREAN_LEVEL_NAMES.items():
        logging.addLevelName(level, name)


def configure_logging(service_name: str) -> None:
    """Configure a compact console logger for demo-friendly frontend/backend logs."""
    _apply_korean_level_names()
    level = _resolve_level()
    logger = logging.getLogger("gongsitalk")
    logger.setLevel(level)
    logger.propagate = False

    for handler in logger.handlers:
        if getattr(handler, "_gongsitalk_service", None) == service_name:
            handler.setLevel(level)
            return

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    log_format = f"%(asctime)s | {service_name} | %(levelname)s | %(message)s"
    handler.setFormatter(logging.Formatter(log_format, DEFAULT_DATE_FORMAT))
    handler._gongsitalk_service = service_name  # type: ignore[attr-defined]
    logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"gongsitalk.{name}")
