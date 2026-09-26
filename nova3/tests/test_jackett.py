from __future__ import annotations

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
def test_jackett_reports_setup_errors(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str],
    response: str | None,
) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1

    def fake_response(_query: str) -> str | None:
        return response

    monkeypatch.setattr(engine, 'get_response', fake_response)
    engine.search('linux', 'all')

    assert capfd.readouterr().err


@pytest.mark.parametrize('response', [
    '<indexers',
    '<error code="100" description="Invalid API Key" />',
])
def test_jackett_raises_for_bad_response(monkeypatch: pytest.MonkeyPatch, response: str) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'

    def fake_response(_query: str) -> str:
        return response

    monkeypatch.setattr(engine, 'get_response', fake_response)

    with pytest.raises(RuntimeError):
        engine.search('linux', 'all')


def test_jackett_checks_indexers_without_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1
    searches: list[tuple[str, list[str] | None, str]] = []

    def fake_response(_query: str) -> str:
        return '<indexers><indexer id="thepiratebay" /></indexers>'

    def fake_search(what: str, category: list[str] | None, indexer_id: str) -> None:
        searches.append((what, category, indexer_id))

    monkeypatch.setattr(engine, 'get_response', fake_response)
    monkeypatch.setattr(engine, 'search_jackett_indexer', fake_search)
    engine.search('linux', 'all')

    assert searches == [('linux', None, 'all')]
