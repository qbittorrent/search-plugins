from typing import Any, Dict

import pytest

from ..engines import eztv


def test_eztv(capfd: pytest.CaptureFixture[str]) -> None:
    engine = eztv.eztv()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0


def test_eztv_api_search(
    monkeypatch: pytest.MonkeyPatch, capfd: pytest.CaptureFixture[str]
) -> None:
    engine = eztv.eztv()

    def fake_json(url: str) -> Dict[str, Any]:
        if "api.tvmaze.com" in url:
            return {"externals": {"imdb": "tt0386676"}}
        assert "imdb_id=0386676" in url
        return {
            "torrents_count": 2,
            "torrents": [
                {
                    "id": 1,
                    "title": "The Office US S09E12 1080p",
                    "magnet_url": "magnet:?xt=urn:btih:one",
                    "size_bytes": 1024,
                    "seeds": 10,
                    "peers": 2,
                    "date_released_unix": 123,
                },
                {
                    "id": 2,
                    "title": "The Office US S09E13 1080p",
                    "magnet_url": "magnet:?xt=urn:btih:two",
                    "size_bytes": 2048,
                    "seeds": 5,
                    "peers": 1,
                    "date_released_unix": 456,
                },
            ],
        }

    monkeypatch.setattr(engine, "_json", fake_json)
    engine.search("the office s09e12", "tv")

    captured_output = capfd.readouterr()
    assert captured_output.err == ""
    assert "The Office US S09E12 1080p" in captured_output.out
    assert "The Office US S09E13 1080p" not in captured_output.out
