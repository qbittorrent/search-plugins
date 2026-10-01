import pytest

from ..engines import torlock


def test_torlock(capfd: pytest.CaptureFixture[str]) -> None:
    engine = torlock.torlock()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
