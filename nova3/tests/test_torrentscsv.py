import pytest

from ..engines import torrentscsv


def test_torrentscsv(capfd: pytest.CaptureFixture[str]) -> None:
    engine = torrentscsv.torrentscsv()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
