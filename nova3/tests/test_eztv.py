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
    urls: list[str] = []

    def fake_json(url: str) -> object:
        urls.append(url)
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
                    "season": "9",
                    "episode": "12",
                },
                {
                    "id": 2,
                    "title": "The Office US S09E13 1080p",
                    "magnet_url": "magnet:?xt=urn:btih:two",
                    "size_bytes": 2048,
                    "seeds": 5,
                    "peers": 1,
                    "date_released_unix": 456,
                    "season": "9",
                    "episode": "13",
                },
            ],
        }

    monkeypatch.setattr(engine, "_json", fake_json)
    engine.search("the office s09e12", "tv")

    captured_output = capfd.readouterr()
    assert captured_output.err == ""
    assert "The Office US S09E12 1080p" in captured_output.out
    assert "The Office US S09E13 1080p" not in captured_output.out
    assert urls == ["https://eztvx.to/api/get-torrents?limit=100&page=1"]


def test_eztv_imdb_id_search(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = eztv.eztv()
    urls: list[str] = []

    def fake_json(url: str) -> object:
        urls.append(url)
        return {"torrents_count": 0, "torrents": []}

    monkeypatch.setattr(engine, "_json", fake_json)
    engine.search("tt0386676")

    assert urls == ["https://eztvx.to/api/get-torrents?limit=100&page=1&imdb_id=0386676"]
