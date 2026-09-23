from typing import List, Optional, Tuple

import pytest

from ..engines import jackett


def test_jackett(capfd: pytest.CaptureFixture[str]) -> None:
    engine = jackett.jackett()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0


def test_jackett_reports_missing_api_key(capfd: pytest.CaptureFixture[str]) -> None:
    engine = jackett.jackett()
    engine.api_key = 'YOUR_API_KEY_HERE'
    engine.search('linux', 'all')

    assert 'API key not configured in jackett.json' in capfd.readouterr().out


@pytest.mark.parametrize(
    ('response', 'message'),
    [
        (None, 'cannot contact Jackett'),
        ('<error code="100" description="Invalid API Key" />', 'Invalid API Key'),
        ('<indexers />', 'no indexers configured in Jackett'),
        ('<indexers', 'invalid response from Jackett'),
    ],
)
def test_jackett_reports_setup_errors(
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
    response: Optional[str],
    message: str,
) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1

    def fake_response(_query: str) -> Optional[str]:
        return response

    monkeypatch.setattr(engine, 'get_response', fake_response)
    engine.search('linux', 'all')

    captured_output = capfd.readouterr()
    assert captured_output.err == ''
    assert message in captured_output.out


def test_jackett_checks_indexers_without_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = jackett.jackett()
    engine.api_key = 'test-key'
    engine.thread_count = 1
    searches: List[Tuple[str, Optional[List[str]], str]] = []

    def fake_response(_query: str) -> Optional[str]:
        return '<indexers><indexer id="thepiratebay" /></indexers>'

    def fake_search(what: str, category: Optional[List[str]], indexer_id: str) -> None:
        searches.append((what, category, indexer_id))

    monkeypatch.setattr(engine, 'get_response', fake_response)
    monkeypatch.setattr(engine, 'search_jackett_indexer', fake_search)
    engine.search('linux', 'all')

    assert searches == [('linux', None, 'all')]
