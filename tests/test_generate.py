from io import StringIO
import sys, subprocess
sys.path.append('src')

from types import SimpleNamespace
from typing import Any
from llm_cli import LLMClient
git_llm_utils = __import__('git-llm-utils')

def _mock_changes(monkeypatch, changes: str | Any):

    def _changes(*args, **kwargs):
        return SimpleNamespace(stdout=changes)

    monkeypatch.setattr(subprocess, 'run', _changes)

def _mock_message(monkeypatch, message: str | Any):

    def _message(*args, **kwargs):
        yield message

    monkeypatch.setattr(LLMClient, 'message', _message)

def _mock(monkeypatch, changes: str | Any = None, message: str | Any = None):
    _mock_changes(monkeypatch, changes=changes)
    _mock_message(monkeypatch, message=message)

def test_generate_manual_does_nothing(monkeypatch):
    _mock(monkeypatch)
    res = StringIO()
    git_llm_utils.generate(manual=True, output=res)
    res.seek(0)
    assert res.read() == ''
    
def test_generate_with_no_change(monkeypatch):
    _mock(monkeypatch)
    res = StringIO()
    git_llm_utils.generate(manual=False, output=res)
    res.seek(0)
    assert res.read() ==  'No changes\n'

def test_generate_with_comments(monkeypatch):
    _mock(monkeypatch, 'test', 'test')
    res = StringIO()
    git_llm_utils.generate(
        manual=False, with_comments=True, description_file=None, with_emojis=False,
        model='test', api_key='test', api_url='test', output=res
    )
    res.seek(0)
    assert res.read() == '# test\n'

def test_generate_without_comments(monkeypatch):
    _mock(monkeypatch, 'test', 'test')
    res = StringIO()
    git_llm_utils.generate(
        manual=False, with_comments=False, description_file=None, with_emojis=False,
        model='test', api_key='test', api_url='test', output=res
    )
    res.seek(0)
    assert res.read() == 'test\n'
