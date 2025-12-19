from io import StringIO
import subprocess
import sys

sys.path.append("src")

from types import SimpleNamespace
from typing import Any
from git_llm_utils.main import generate, NO_CHANGES_MESSAGE
from git_llm_utils.llm_cli import LLMClient


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
    generate(
        manual=True,
        manual_override=False,
        output=res,
        max_input_tokens=1000,
        max_output_tokens=1000,
    )
    res.seek(0)
    assert res.read() == ""


def test_generate_with_no_change(monkeypatch):
    _mock(monkeypatch)
    res = StringIO()
    generate(
        manual=False,
        manual_override=True,
        output=res,
        max_input_tokens=1000,
        max_output_tokens=1000,
    )
    res.seek(0)
    assert res.read() == f"{NO_CHANGES_MESSAGE}\n"


def test_generate_with_comments(monkeypatch):
    _mock(monkeypatch, "test", "test")
    res = StringIO()
    generate(
        manual=False,
        manual_override=True,
        with_comments=True,
        description_file=None,
        with_emojis=False,
        model="test",
        max_input_tokens=1000,
        max_output_tokens=1000,
        api_key="test",
        api_url="test",
        output=res,
    )
    res.seek(0)
    assert res.read() == "# test\n"


def test_generate_without_comments(monkeypatch):
    _mock(monkeypatch, "test", "test")
    res = StringIO()
    generate(
        manual=False,
        manual_override=True,
        with_comments=False,
        description_file=None,
        with_emojis=False,
        model="test",
        max_input_tokens=1000,
        max_output_tokens=1000,
        api_key="test",
        api_url="test",
        output=res,
    )
    res.seek(0)
    assert res.read() == "test\n"
