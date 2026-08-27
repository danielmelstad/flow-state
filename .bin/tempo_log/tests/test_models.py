from datetime import time

from tempo_log.models import Window


def test_window_parse_and_seconds():
    w = Window.parse("08:00-16:00")
    assert w.start == time(8, 0)
    assert w.end == time(16, 0)
    assert w.seconds == 8 * 3600


def test_window_rejects_inverted():
    import pytest

    with pytest.raises(ValueError):
        Window.parse("16:00-08:00")
