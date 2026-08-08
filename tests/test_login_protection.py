import pytest

from app.services.login_protection import LoginRateLimiter

pytestmark = pytest.mark.no_database


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_limiter(clock: FakeClock, *, max_clients: int = 10) -> LoginRateLimiter:
    return LoginRateLimiter(
        max_failures=3,
        window_seconds=60,
        max_clients=max_clients,
        clock=clock,
    )


def test_blocks_after_limit_and_expires_without_sleep() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)

    for _ in range(3):
        assert limiter.check("192.0.2.1").limited is False
        limiter.record_failure("192.0.2.1")

    decision = limiter.check("192.0.2.1")
    assert decision.limited is True
    assert decision.retry_after == 60

    clock.advance(60)
    assert limiter.check("192.0.2.1").limited is False


def test_success_clears_failures_and_clients_are_isolated() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)

    for _ in range(3):
        limiter.record_failure("192.0.2.1")

    assert limiter.check("192.0.2.1").limited is True
    assert limiter.check("198.51.100.2").limited is False

    limiter.record_success("192.0.2.1")
    assert limiter.check("192.0.2.1").limited is False


def test_storage_is_bounded_and_expired_entries_are_removed() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, max_clients=2)

    limiter.record_failure("192.0.2.1")
    limiter.record_failure("192.0.2.2")
    limiter.record_failure("192.0.2.3")

    assert len(limiter._failures) == 2
    assert "192.0.2.1" not in limiter._failures

    clock.advance(60)
    limiter.record_failure("192.0.2.4")
    assert list(limiter._failures) == ["192.0.2.4"]

