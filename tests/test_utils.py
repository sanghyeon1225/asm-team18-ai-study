import pytest

from src.utils import get_required_env


def test_get_required_env_returns_value(monkeypatch) -> None:
    monkeypatch.setenv("SAMPLE_KEY", " sample-value ")

    assert get_required_env("SAMPLE_KEY") == "sample-value"


def test_get_required_env_raises_for_missing_value(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_SAMPLE_KEY", raising=False)

    with pytest.raises(ValueError, match="MISSING_SAMPLE_KEY"):
        get_required_env("MISSING_SAMPLE_KEY")
