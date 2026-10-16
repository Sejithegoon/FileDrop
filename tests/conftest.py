import pytest


@pytest.fixture(autouse=True)
def _fresh_rate_limiter():
    """Every test starts with an empty per-IP sign-in counter (it lives in memory)."""
    from app.services import auth
    auth.ip_limiter.clear()
    yield
    auth.ip_limiter.clear()
