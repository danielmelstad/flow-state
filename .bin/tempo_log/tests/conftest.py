from datetime import datetime, timezone

import pytest


@pytest.fixture
def utc():
    def _utc(y, mo, d, h=0, mi=0, s=0):
        return datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)

    return _utc
