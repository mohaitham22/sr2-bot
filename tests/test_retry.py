"""Tests for app/services/retry.py (Step 2.4).

A fake clock and a fake sleep: the waits are recorded, and time moves only when the test says so,
so no test really waits (except one short real-time check of the deadline timer, 0.05 s).
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable

import pytest

from app.services.retry import DEFAULT_POLICY, Retried, RetryGaveUp, RetryPolicy, retry_async

SECRET_TEXT = "+201001234567 Ahmed Fake"  # stands for what a server error text could contain


class Retryable(Exception):
    """A short problem (like HTTP 429 or 503). `retry_after` = the wait the server asked for."""

    def __init__(self, retry_after: float | None = None) -> None:
        super().__init__(SECRET_TEXT)
        self.retry_after = retry_after


class NotRetryable(Exception):
    """A problem another try can't fix (like HTTP 401 wrong key)."""


class FakeTime:
    """A clock that moves only on sleep() or advance(); every wait is recorded."""

    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


def scripted_call(
    outcomes: list[object], fake_time: FakeTime | None = None, seconds_per_try: float = 0.0
) -> tuple[Callable[[], Awaitable[object]], list[int]]:
    """A call that returns or raises the next outcome; each try takes `seconds_per_try` (fake)."""
    calls: list[int] = []

    async def call() -> object:
        calls.append(1)
        if fake_time is not None:
            fake_time.now += seconds_per_try
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return call, calls


def run_retry(
    call: Callable[[], Awaitable[object]],
    fake_time: FakeTime,
    policy: RetryPolicy = DEFAULT_POLICY,
    fraction: float = 0.5,
) -> Retried[object]:
    """retry_async with the fake clock, a fixed "random" fraction, and the usual test rules."""
    return asyncio.run(
        retry_async(
            call,
            is_retryable=lambda error: isinstance(error, Retryable | TimeoutError),
            retry_after=lambda error: getattr(error, "retry_after", None),
            policy=policy,
            sleep=fake_time.sleep,
            random_fraction=lambda: fraction,
            clock=fake_time.clock,
        )
    )


def test_first_try_works() -> None:
    fake_time = FakeTime()
    call, calls = scripted_call(["answer"])

    result = run_retry(call, fake_time)

    assert result == Retried("answer", tries=1)
    assert len(calls) == 1
    assert fake_time.waits == []


def test_retryable_errors_then_success_with_full_jitter() -> None:
    fake_time = FakeTime()
    call, _ = scripted_call([Retryable(), Retryable(), "answer"])

    result = run_retry(call, fake_time, fraction=0.5)

    assert result == Retried("answer", tries=3)
    # Full jitter: fraction x min(8, 1 x 2 ** (try - 1)) -> 0.5 x 1, then 0.5 x 2
    assert fake_time.waits == [0.5, 1.0]


def test_longest_wait_doubles_until_the_cap() -> None:
    fake_time = FakeTime()
    call, _ = scripted_call([Retryable()] * 5 + ["answer"])
    policy = RetryPolicy(max_tries=6, deadline_seconds=100)

    result = run_retry(call, fake_time, policy, fraction=1.0)  # 1.0 = the longest possible wait

    assert result.tries == 6
    assert fake_time.waits == [1.0, 2.0, 4.0, 8.0, 8.0]  # 16 would be over the 8 s cap


def test_not_retryable_goes_up_at_once_unchanged() -> None:
    fake_time = FakeTime()
    error = NotRetryable("wrong key")
    call, calls = scripted_call([error, "never reached"])

    with pytest.raises(NotRetryable) as raised:
        run_retry(call, fake_time)

    assert raised.value is error
    assert len(calls) == 1
    assert fake_time.waits == []


def test_gives_up_after_max_tries() -> None:
    fake_time = FakeTime()
    last = Retryable()
    call, calls = scripted_call([Retryable(), Retryable(), last])

    with pytest.raises(RetryGaveUp) as raised:
        run_retry(call, fake_time)

    assert raised.value.reason == "max_tries"
    assert raised.value.tries == 3
    assert raised.value.last_error is last
    assert len(calls) == 3
    assert len(fake_time.waits) == 2  # no wait after the last try


def test_gave_up_error_hides_the_last_error_text() -> None:
    fake_time = FakeTime()
    call, _ = scripted_call([Retryable(), Retryable(), Retryable()])

    with pytest.raises(RetryGaveUp) as raised:
        run_retry(call, fake_time)

    # Not in the message, and not chained, so a traceback never prints it
    assert SECRET_TEXT not in str(raised.value)
    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True


def test_server_retry_after_is_used_instead_of_jitter() -> None:
    fake_time = FakeTime()
    call, _ = scripted_call([Retryable(retry_after=3.0), "answer"])

    result = run_retry(call, fake_time)

    assert result.tries == 2
    assert fake_time.waits == [3.0]


def test_too_long_retry_after_stops_at_once() -> None:
    fake_time = FakeTime()
    call, calls = scripted_call([Retryable(retry_after=11.0), "never reached"])  # 11 > 10

    with pytest.raises(RetryGaveUp) as raised:
        run_retry(call, fake_time)

    assert raised.value.reason == "retry_after_too_long"
    assert raised.value.tries == 1
    assert len(calls) == 1
    assert fake_time.waits == []  # no point waiting for a daily limit


def test_wait_that_would_cross_the_deadline_stops_at_once() -> None:
    fake_time = FakeTime()
    # Each try takes 9 s: try 1 ends at 9 s, wait 1 s; try 2 ends at 19 s; a 2 s wait -> 21 s > 20
    call, calls = scripted_call([Retryable(), Retryable(), "never reached"], fake_time, 9.0)

    with pytest.raises(RetryGaveUp) as raised:
        run_retry(call, fake_time, fraction=1.0)

    assert raised.value.reason == "deadline"
    assert raised.value.tries == 2
    assert len(calls) == 2
    assert fake_time.waits == [1.0]


def test_wait_that_took_longer_than_planned_stops() -> None:
    fake_time = FakeTime()

    async def slow_sleep(seconds: float) -> None:  # e.g. a busy laptop: 0.5 s became 30 s
        fake_time.now += 30

    call, calls = scripted_call([Retryable(), "never reached"])

    with pytest.raises(RetryGaveUp) as raised:
        asyncio.run(
            retry_async(
                call,
                is_retryable=lambda error: isinstance(error, Retryable),
                sleep=slow_sleep,
                random_fraction=lambda: 0.5,
                clock=fake_time.clock,
            )
        )

    assert raised.value.reason == "deadline"
    assert len(calls) == 1


def test_deadline_stops_a_try_that_hangs() -> None:
    """Real time: a try that never ends is stopped by the deadline timer, not after 5 s."""

    async def hangs() -> str:
        await asyncio.sleep(5)
        return "too late"

    policy = RetryPolicy(deadline_seconds=0.05)
    start = time.monotonic()

    with pytest.raises(RetryGaveUp) as raised:
        asyncio.run(retry_async(hangs, is_retryable=lambda error: True, policy=policy))

    assert time.monotonic() - start < 1.0
    assert raised.value.reason == "deadline"
    assert raised.value.tries == 1


def test_timeout_error_from_the_call_itself_is_not_the_deadline() -> None:
    """Only our own timer means "deadline"; a TimeoutError raised inside the call is retried."""
    fake_time = FakeTime()
    call, _ = scripted_call([TimeoutError(), "answer"])

    result = run_retry(call, fake_time)

    assert result == Retried("answer", tries=2)


def test_log_names_the_error_but_never_its_text(caplog: pytest.LogCaptureFixture) -> None:
    fake_time = FakeTime()
    call, _ = scripted_call([Retryable(), "answer"])
    caplog.set_level(logging.WARNING, logger="app.services.retry")

    asyncio.run(
        retry_async(
            call,
            is_retryable=lambda error: True,
            describe=lambda error: "HTTP 503 (over_capacity)",
            label="llm extract",
            sleep=fake_time.sleep,
            random_fraction=lambda: 0.5,
            clock=fake_time.clock,
        )
    )

    assert "llm extract: HTTP 503 (over_capacity) on try 1 of 3, waiting 0.50 s" in caplog.text
    assert SECRET_TEXT not in caplog.text


@pytest.mark.parametrize(
    "values",
    [
        {"max_tries": 0},
        {"base_seconds": 0},
        {"cap_seconds": -1},
        {"deadline_seconds": 0},
        {"max_retry_after_seconds": -1},
    ],
)
def test_policy_refuses_impossible_values(values: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**values)
