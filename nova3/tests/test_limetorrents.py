import pytest

from ..engines import limetorrents


def test_limetorrents(capfd: pytest.CaptureFixture[str]) -> None:
    engine = limetorrents.limetorrents()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
