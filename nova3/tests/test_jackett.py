from __future__ import annotations

from unittest.mock import Mock

import pytest

from ..engines import jackett


def test_jackett(capfd: pytest.CaptureFixture[str]) -> None:
    engine = jackett.jackett()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err or capturedOutput.out


def test_jackett_reports_missing_api_key(capfd: pytest.CaptureFixture[str]) -> None:
    engine = jackett.jackett()
    engine.api_key = 'YOUR_API_KEY_HERE'
    engine.search('linux', 'all')

    assert capfd.readouterr().err


@pytest.mark.parametrize(
    'response',
    [
        None,
        '<indexers />',
    ],
)
def test_jackett_reports_setup_errors(monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str], response: str | None) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1

    monkeypatch.setattr(engine, 'get_response', Mock(return_value=response))
    engine.search('linux', 'all')

    assert capfd.readouterr().err


@pytest.mark.parametrize('response', [
    '<indexers',
    '<error code="100" description="Invalid API Key" />',
])
def test_jackett_raises_for_bad_response(monkeypatch: pytest.MonkeyPatch, response: str) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'

    monkeypatch.setattr(engine, 'get_response', Mock(return_value=response))

    with pytest.raises(RuntimeError):
        engine.search('linux', 'all')


def test_jackett_checks_indexers_without_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1
    search_mock = Mock()
    monkeypatch.setattr(engine, 'get_response', Mock(return_value='<indexers><indexer id="thepiratebay" /></indexers>'))
    monkeypatch.setattr(engine, 'search_jackett_indexer', search_mock)
    engine.search('linux', 'all')

    search_mock.assert_called_once_with('linux', None, 'all')
