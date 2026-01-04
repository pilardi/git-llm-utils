from io import StringIO
import subprocess
import sys

sys.path.append("src")

from types import SimpleNamespace
from typing import Any
from git_llm_utils.app import generate, Runtime, Setting, NO_CHANGES_MESSAGE
from git_llm_utils.llm import LLMClient


def _mock_changes(monkeypatch, changes: str | Any):
    def _changes(*args, **kwargs):
        return SimpleNamespace(stdout=changes)

    monkeypatch.setattr(subprocess, "run", _changes)


def _mock_message(monkeypatch, message: str | Any):
    def _message(*args, **kwargs):
        yield message

    monkeypatch.setattr(LLMClient, "message", _message)


def _mock(monkeypatch, changes: str | Any = None, message: str | Any = None):
    _mock_changes(monkeypatch, changes=changes)
    _mock_message(monkeypatch, message=message)


def test_generate_manual_does_nothing(monkeypatch):
    _mock(monkeypatch)
    res = StringIO()
    Runtime.set_value(Setting.MAX_INPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.MAX_OUTPUT_TOKENS.value, 1000)
    generate(
        manual=True,
        manual_override=False,
        output=res,
    )
    res.seek(0)
    assert res.read() == ""


def test_generate_with_no_change(monkeypatch):
    _mock(monkeypatch)
    res = StringIO()
    Runtime.set_value(Setting.MAX_INPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.MAX_OUTPUT_TOKENS.value, 1000)
    generate(
        manual=False,
        manual_override=True,
        output=res,
    )
    res.seek(0)
    assert res.read() == f"{NO_CHANGES_MESSAGE}\n"


def test_generate_with_comments(monkeypatch):
    _mock(monkeypatch, "test", "test")
    Runtime.set_value(Setting.MODEL.value, "test")
    Runtime.set_value(Setting.API_KEY.value, "test")
    Runtime.set_value(Setting.API_URL.value, "test")
    Runtime.set_value(Setting.MODEL_REASONING.value, "high")
    Runtime.set_value(Setting.MAX_INPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.MAX_OUTPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.EMOJIS.value, False)
    Runtime.set_value(Setting.DESCRIPTION_FILE.value, None)
    res = StringIO()
    generate(
        manual=False,
        manual_override=True,
        with_comments=True,
        output=res,
    )
    res.seek(0)
    assert res.read() == "# test"


def test_generate_without_comments(monkeypatch):
    _mock(monkeypatch, "test", "test")
    Runtime.set_value(Setting.MODEL.value, "test")
    Runtime.set_value(Setting.API_KEY.value, "test")
    Runtime.set_value(Setting.API_URL.value, "test")
    Runtime.set_value(Setting.MODEL_REASONING.value, "high")
    Runtime.set_value(Setting.MAX_INPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.MAX_OUTPUT_TOKENS.value, 1000)
    Runtime.set_value(Setting.EMOJIS.value, False)
    Runtime.set_value(Setting.DESCRIPTION_FILE.value, None)
    res = StringIO()
    generate(
        manual=False,
        manual_override=True,
        with_comments=False,
        output=res,
    )
    res.seek(0)
    assert res.read() == "test"
