"""Retry an async call with exponential backoff and full jitter, inside a total deadline.

Generic: this module knows nothing about LLMs or HTTP. The caller says which errors are worth
another try and how long the server asked us to wait (Step 2.4 D3 A, Momo's changes 1 and 10).
"""

import asyncio
import logging
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

# Why we stopped trying: all tries failed / no time left / the server asked for a too-long wait
GiveUpReason = Literal["max_tries", "deadline", "retry_after_too_long"]


@dataclass(frozen=True)
class RetryPolicy:
    """How many tries, how long to wait between them, and the time limit for all of them."""

    max_tries: int = 3  # the first try + 2 retries
    base_seconds: float = 1.0  # the longest first wait; it doubles after each failed try ...
    cap_seconds: float = 8.0  # ... but one wait is never longer than this
    # A server that asks for a longer wait (e.g. a daily limit is used up) won't be ready soon:
    # stop at once instead of keeping the user waiting
    max_retry_after_seconds: float = 10.0
    deadline_seconds: float = 20.0  # all tries and waits together

    def __post_init__(self) -> None:
        if self.max_tries < 1:
            raise ValueError("max_tries must be at least 1")
        seconds = (self.base_seconds, self.cap_seconds, self.deadline_seconds)
        if min(seconds) <= 0 or self.max_retry_after_seconds < 0:
            raise ValueError("RetryPolicy times must be above 0")


DEFAULT_POLICY = RetryPolicy()


@dataclass(frozen=True)
class Retried[T]:
    """The value of the try that worked, and how many tries it took (1 = no retry)."""

    value: T
    tries: int


class RetryGaveUp(Exception):
    """Every try failed, or there was no time left for another one.

    The message holds only the reason and the number of tries. The last error is kept in
    `last_error` for the caller, but it is not chained (`from None`): its text may come from a
    server and contain anything, so a traceback of this error never prints it.
    """

    def __init__(self, reason: GiveUpReason, tries: int, last_error: Exception) -> None:
        super().__init__(f"gave up after {tries} tries: {reason}")
        self.reason: GiveUpReason = reason
        self.tries = tries
        self.last_error = last_error


def _no_retry_after(error: Exception) -> float | None:
    return None


def _error_type(error: Exception) -> str:
    return type(error).__name__


async def retry_async[T](
    call: Callable[[], Awaitable[T]],
    *,
    is_retryable: Callable[[Exception], bool],
    retry_after: Callable[[Exception], float | None] = _no_retry_after,
    describe: Callable[[Exception], str] = _error_type,
    policy: RetryPolicy = DEFAULT_POLICY,
    label: str = "call",
    sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
    random_fraction: Callable[[], float] = random.random,
    clock: Callable[[], float] = time.monotonic,
) -> Retried[T]:
    """Run `call` until it works: at most `policy.max_tries` times, within the deadline.

    - An error that is not retryable goes up to the caller at once, unchanged.
    - After a retryable error, wait: the server's retry-after if it sent one, else "full jitter":
      a random time between 0 and min(cap, base * 2 ** (try - 1)), so 0-1 s, 0-2 s, 0-4 s, ...
    - Give up (RetryGaveUp) when the tries are used up, when the server asks for a wait longer
      than `max_retry_after_seconds`, or when a wait or a try would end after the deadline.

    `describe` turns an error into a short, safe text for the log (default: its type name).
    The error's own message is never logged: it may contain what we sent.
    `sleep`, `random_fraction` and `clock` are parameters so tests never really wait.
    """
    start = clock()
    for attempt in range(1, policy.max_tries + 1):
        # Stops a try that would end after the deadline: try 2 gets only the time that is left
        timer = asyncio.timeout(policy.deadline_seconds - (clock() - start))
        try:
            async with timer:
                return Retried(await call(), attempt)
        except Exception as error:
            if timer.expired():  # our timer stopped the try (asyncio raised TimeoutError)
                raise RetryGaveUp("deadline", attempt, error) from None
            if not is_retryable(error):
                raise
            last_error = error

        if attempt == policy.max_tries:
            raise RetryGaveUp("max_tries", attempt, last_error) from None
        asked = retry_after(last_error)
        if asked is not None and asked > policy.max_retry_after_seconds:
            raise RetryGaveUp("retry_after_too_long", attempt, last_error) from None
        if asked is not None:
            wait = max(0.0, asked)
        else:
            longest = min(policy.cap_seconds, policy.base_seconds * 2 ** (attempt - 1))
            wait = random_fraction() * longest
        if clock() - start + wait >= policy.deadline_seconds:
            raise RetryGaveUp("deadline", attempt, last_error) from None

        logger.warning(
            "%s: %s on try %d of %d, waiting %.2f s",
            label,
            describe(last_error),
            attempt,
            policy.max_tries,
            wait,
        )
        await sleep(wait)
        if clock() - start >= policy.deadline_seconds:  # the wait took longer than planned
            raise RetryGaveUp("deadline", attempt, last_error) from None

    raise AssertionError("unreachable: the last try returns or raises")  # for type checkers
