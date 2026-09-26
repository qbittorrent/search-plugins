import pytest

from ..engines import jackett


def test_jackett(capfd: pytest.CaptureFixture[str]) -> None:
    engine = jackett.jackett()
    engine.search('linux', 'all')

    capturedOutput = capfd.readouterr()
    assert capturedOutput.err == ""
    assert len(capturedOutput.out) >= 0
