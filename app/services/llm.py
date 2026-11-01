"""The one place in the app that talks to an LLM (Step 2.4).

The rest of the app calls `LLMClient.complete()` (a text answer) or `complete_json()` (an answer
checked against a Pydantic model) and never knows which provider answered. Switching between
Groq and Gemini is a .env change: LLM_PROVIDER + LLM_MODEL (D1 A: one OpenAI-compatible client).

Privacy (CLAUDE.md section 9): messages and answers can contain a name or phone. They are never
logged, never put in an error message and never written to the usage file. Only numbers and
codes are recorded (D4 A, D5 B).
"""

import asyncio
import logging
import math
import random
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal

import httpx2
import openai
from openai.types.chat import ChatCompletion
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

from app.config import LLMProvider, Settings
from app.services.retry import (
    DEFAULT_POLICY,
    GiveUpReason,
    RetryGaveUp,
    RetryPolicy,
    retry_async,
)

logger = logging.getLogger(__name__)


# --- Providers ---


@dataclass(frozen=True)
class ProviderInfo:
    """Where a provider's OpenAI-compatible API is, and which setting holds its key."""

    base_url: str
    key_setting: str  # a field of app.config.Settings


# The usual addresses: the same on the laptop and the server, so they live here (smaller
# choice 3); LLM_BASE_URL replaces them if ever needed. Azure OpenAI: later (stretch S12).
PROVIDERS: dict[LLMProvider, ProviderInfo] = {
    "groq": ProviderInfo("https://api.groq.com/openai/v1", "groq_api_key"),
    "gemini": ProviderInfo(
        "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini_api_key"
    ),
}


# --- What goes in ---

# system = the rules; user = what the person wrote; assistant = what the model said before
ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """One message for the LLM. Phase 3 turns our stored role "bot" into "assistant"."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    role: ChatRole
    content: str = Field(min_length=1, repr=False)  # may hold a name or phone: never printed


# --- What we record for every call (D4 A, D5 B) ---

Outcome = Literal["ok", "invalid_output", "refused", "unavailable"]

# A task is a label from our code, e.g. "extract" or "smoke_test", never text from a user
TASK_PATTERN = r"^[a-z0-9_]{1,40}$"
# A code from a provider or from Pydantic looks like "rate_limit_exceeded" or "INVALID_ARGUMENT"
SAFE_CODE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")


def safe_code(value: object) -> str | None:
    """Keep a code only if it looks like one; anything else becomes "other".

    Codes (error codes, finish reasons, field names) come from the provider or from Pydantic.
    They should never hold user text, and this makes sure that one that did could not reach a
    log, an error message or the usage file (Momo's change 7).
    """
    if value is None:
        return None
    text = str(value)
    return text if SAFE_CODE.fullmatch(text) else "other"


class LLMUsage(BaseModel):
    """The numbers of one LLM call: one log line, and one JSON line in LLM_USAGE_FILE.

    No field can hold text we sent or got: `task` must match TASK_PATTERN, and the codes pass
    safe_code(). `extra="forbid"`: nobody can add a field by mistake.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    time: datetime  # when the call ended, in UTC
    provider: LLMProvider
    model: str  # the model we asked for (LLM_MODEL)
    task: str = Field(pattern=TASK_PATTERN)
    outcome: Outcome
    tries: int
    total_ms: int  # all tries and waits together: what the user waits
    latency_ms: int | None  # only the try that worked (the model's speed); None if none did
    # Token counts as the provider reports them; None = it didn't say
    input_tokens: int | None
    output_tokens: int | None  # thinking included
    reasoning_tokens: int | None  # the thinking part of output_tokens (Momo's change 5)
    finish_reason: str | None  # "stop" = finished; "length" = cut off by max_output_tokens
    http_status: int | None  # of the last failed try
    error_code: str | None  # the provider's, e.g. "invalid_api_key"; or ours, e.g. "timeout"
    give_up_reason: GiveUpReason | None  # why the retries stopped (app/services/retry.py)


def record_usage(usage: LLMUsage, usage_file: Path | None) -> None:
    """Write the numbers of one call: a log line, and a JSON line if a file is set (D5 B).

    The file write is a plain append, not async: it takes microseconds, like a log line, and
    asyncio runs one piece of code at a time, so two lines can't mix. A file problem (disk full,
    no permission) is logged and skipped: the user's answer matters more than the numbers.
    """
    logger.log(
        logging.INFO if usage.outcome == "ok" else logging.WARNING,
        "llm %s: %s, provider=%s model=%s tries=%d total_ms=%d latency_ms=%s "
        "tokens in=%s out=%s reasoning=%s finish=%s http=%s code=%s gave_up=%s",
        usage.task,
        usage.outcome,
        usage.provider,
        usage.model,
        usage.tries,
        usage.total_ms,
        usage.latency_ms,
        usage.input_tokens,
        usage.output_tokens,
        usage.reasoning_tokens,
        usage.finish_reason,
        usage.http_status,
        usage.error_code,
        usage.give_up_reason,
    )
    if usage_file is None:
        return
    try:
        usage_file.parent.mkdir(parents=True, exist_ok=True)
        with usage_file.open("a", encoding="utf-8") as file:
            file.write(usage.model_dump_json() + "\n")
    except OSError as error:
        logger.warning("Could not write the LLM usage file: %s", type(error).__name__)


# --- What comes out ---


@dataclass(frozen=True)
class LLMText:
    """A text answer and its numbers."""

    text: str = field(repr=False)
    usage: LLMUsage


@dataclass(frozen=True)
class LLMJson[T: BaseModel]:
    """An answer checked against the Pydantic model T, and its numbers."""

    data: T = field(repr=False)
    usage: LLMUsage


# --- Errors ---


class LLMError(Exception):
    """Base of our LLM errors. The message holds names, codes and numbers, never text.

    `usage` holds the numbers of the failed call (they are also in the log and the usage file),
    so `http_status` and `error_code` come from there. The provider's own error is never chained
    (`raise ... from None`): its text may repeat what we sent (lesson of debt T11).
    """

    def __init__(self, message: str, usage: LLMUsage) -> None:
        super().__init__(message)
        self.usage = usage

    @property
    def http_status(self) -> int | None:
        return self.usage.http_status

    @property
    def error_code(self) -> str | None:
        return self.usage.error_code


class LLMUnavailable(LLMError):
    """No answer in time: still failing after the retries (429, 5xx, timeout, network), or the
    total time is up. Phase 3 replies "please try again"."""


class LLMRequestRefused(LLMError):
    """The provider refused the request itself, e.g. 401 wrong key or 404 unknown model.
    Another try can't help: fix .env or the code."""


@dataclass(frozen=True)
class OutputProblem:
    """One reason why an answer doesn't fit the schema. Names and codes only, never values."""

    location: str  # the field, e.g. "unit_number"; "(answer)" = the whole answer
    kind: str  # Pydantic's, e.g. "missing"; or "cut_off", "json_validate_failed"


class LLMOutputInvalid(LLMError):
    """The answer doesn't fit the schema, or it was cut off. Step 2.9 re-asks once with
    `problems`, then asks the user directly (CLAUDE.md section 10)."""

    def __init__(self, message: str, usage: LLMUsage, problems: tuple[OutputProblem, ...]) -> None:
        super().__init__(message, usage)
        self.problems = problems


# --- Strict structured outputs (D2 A) ---


def strict_json_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """The JSON Schema of a Pydantic model, checked against the rules of strict mode.

    Strict mode needs, for every object: every property in "required" (a missing value is null,
    never left out) and "additionalProperties": false. A model that breaks a rule fails here, at
    once and with the field's name, not later as an HTTP 400 from the provider.
    How a model follows the rules: `model_config = ConfigDict(extra="forbid")`, and no defaults:
    `phone: str | None` (must be there, may be null), not `phone: str | None = None`.
    """
    json_schema = schema.model_json_schema()
    _check_strict(json_schema, schema.__name__)
    return json_schema


def _check_strict(node: object, model_name: str) -> None:
    """Walk the whole schema, nested models ($defs) included, and check every object."""
    if isinstance(node, dict):
        if node.get("type") == "object":
            name = node.get("title", model_name)
            if node.get("additionalProperties") is not False:
                raise TypeError(f"{name}: strict mode needs model_config extra='forbid'")
            not_required = set(node.get("properties", {})) - set(node.get("required", []))
            if not_required:
                raise TypeError(
                    f"{name}: strict mode needs every field required (no default): "
                    f"{sorted(not_required)}"
                )
        for value in node.values():
            _check_strict(value, model_name)
    elif isinstance(node, list):
        for item in node:
            _check_strict(item, model_name)


# --- Which errors are worth another try (D3 A) ---

DEFAULT_MAX_OUTPUT_TOKENS = 1024  # thinking tokens count too (smaller choice 5)
# 408 request timeout, 429 too many requests, and every 5xx; also timeouts and lost connections
RETRYABLE_STATUSES = frozenset({408, 429})
# Groq's code for "the model could not make valid JSON" (HTTP 400), seen even in strict mode.
# A problem with the answer, not with our request: LLMOutputInvalid, not refused (change 7)
JSON_FAILED_CODE = "json_validate_failed"


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, openai.APIConnectionError):  # also APITimeoutError (one try too slow)
        return True
    if isinstance(error, openai.APIStatusError):
        return error.status_code in RETRYABLE_STATUSES or error.status_code >= 500
    return False


def _retry_after(error: Exception) -> float | None:
    """The wait the server asked for in its retry-after header, in seconds, if it sent one."""
    if not isinstance(error, openai.APIStatusError):
        return None
    try:
        seconds = float(error.response.headers.get("retry-after", ""))
    except ValueError:  # not sent, or a date: then our own backoff
        return None
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


def _http_status(error: Exception) -> int | None:
    return error.status_code if isinstance(error, openai.APIStatusError) else None


def _error_code(error: Exception) -> str | None:
    """The provider's code (e.g. "invalid_api_key"), or ours for errors without an HTTP answer."""
    if isinstance(error, openai.APIStatusError):
        return safe_code(error.code)
    if isinstance(error, openai.APITimeoutError | TimeoutError):  # TimeoutError: our deadline
        return "timeout"
    if isinstance(error, openai.APIConnectionError):
        return "connection_error"
    return safe_code(type(error).__name__)


def _describe(error: Exception) -> str:
    """A short, safe text for logs and our error messages, e.g. "HTTP 429 (rate_limit_exceeded)".

    Never the provider's message: it may repeat what we sent (Groq's failed_generation does).
    """
    status = _http_status(error)
    code = _error_code(error)
    if status is None:
        return str(code)  # e.g. "timeout": no HTTP answer at all
    return f"HTTP {status} ({code})" if code is not None else f"HTTP {status}"


def _location(loc: tuple[int | str, ...]) -> str:
    """Pydantic's error location, e.g. ("unit", "building") -> "unit.building"."""
    joined = ".".join(str(part) for part in loc)
    return (safe_code(joined) or "other") if joined else "(answer)"


# --- The client ---


class LLMClient:
    """Talks to one provider and one model. Make it once at startup (make_llm_client), share it.

    Every call gets a timeout per try, retries with backoff and jitter inside a total deadline
    (app/services/retry.py), and exactly one LLMUsage record (log line + usage file), whether it
    works or not.
    """

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        api_key: str,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
        retry_policy: RetryPolicy = DEFAULT_POLICY,
        usage_file: Path | None = None,
        http_client: httpx2.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[object]] = asyncio.sleep,
        random_fraction: Callable[[], float] = random.random,
    ) -> None:
        self.provider: LLMProvider = provider
        self.model = model
        self._retry_policy = retry_policy
        self._usage_file = usage_file
        self._sleep = sleep  # tests pass fakes for these two, so they never really wait
        self._random_fraction = random_fraction
        self._client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url or PROVIDERS[provider].base_url,
            timeout=timeout_seconds,  # per try; the total is the retry policy's deadline
            max_retries=0,  # the SDK's own hidden retry is off: retry_async() does it (D3 A)
            http_client=http_client,  # tests pass a fake server here; None = the SDK's own
        )

    async def close(self) -> None:
        """Close the connections. Call once when the app stops."""
        await self._client.close()

    async def list_models(self) -> list[str]:
        """The model names this key may use. Costs no tokens; a setup check, so no retry."""
        return sorted([model.id async for model in self._client.models.list()])

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        task: str,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> LLMText:
        """A text answer. Temperature has no default: each caller chooses (smaller choice 4)."""
        answer = await self._send(
            messages, temperature=temperature, task=task, max_output_tokens=max_output_tokens
        )
        record_usage(answer.usage, self._usage_file)
        return answer

    async def complete_json[T: BaseModel](
        self,
        messages: Sequence[ChatMessage],
        schema: type[T],
        *,
        temperature: float,
        task: str,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    ) -> LLMJson[T]:
        """An answer that fits `schema`: strict structured outputs (D2 A), checked by Pydantic.

        The server makes the shape right; Pydantic checks it again with every rule of the model
        (patterns, our validators in Step 2.8). An answer that doesn't fit: LLMOutputInvalid,
        with the problems by field and kind (never the values) for Step 2.9's re-ask.
        """
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": strict_json_schema(schema),
                "strict": True,
            },
        }
        answer = await self._send(
            messages,
            temperature=temperature,
            task=task,
            max_output_tokens=max_output_tokens,
            response_format=response_format,
        )
        try:
            data = schema.model_validate_json(answer.text)
        except ValidationError as error:
            # include_input=False: Pydantic leaves the values out (they may be a name or phone)
            problems = tuple(
                OutputProblem(_location(item["loc"]), safe_code(item["type"]) or "other")
                for item in error.errors(include_input=False, include_url=False)
            )
            listed = ", ".join(f"{problem.location} ({problem.kind})" for problem in problems[:5])
            usage = answer.usage.model_copy(update={"outcome": "invalid_output"})
            raise self._recorded(
                LLMOutputInvalid(
                    f"Answer does not fit {schema.__name__}: {listed}", usage, problems
                )
            ) from None
        record_usage(answer.usage, self._usage_file)
        return LLMJson(data, answer.usage)

    def _recorded[E: LLMError](self, error: E) -> E:
        """Record a failed call's numbers, then hand the error back to be raised."""
        record_usage(error.usage, self._usage_file)
        return error

    async def _send(
        self,
        messages: Sequence[ChatMessage],
        *,
        temperature: float,
        task: str,
        max_output_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMText:
        """Send one request, with retries. Returns the text with its numbers, not yet recorded
        (complete_json may still find the answer invalid). A failure is recorded and raised."""
        if not messages:
            raise ValueError("messages must not be empty")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if max_output_tokens < 1:
            raise ValueError("max_output_tokens must be at least 1")
        if not re.fullmatch(TASK_PATTERN, task):  # checked before sending, not after
            raise ValueError(f"task must match {TASK_PATTERN}, e.g. 'extract'")

        request: dict[str, Any] = {
            "model": self.model,
            "messages": [message.model_dump() for message in messages],
            "temperature": temperature,
            "max_completion_tokens": max_output_tokens,
        }
        if response_format is not None:
            request["response_format"] = response_format

        started = perf_counter()
        tries = 0
        latency: float | None = None  # of the try that worked

        async def one_try() -> ChatCompletion:
            nonlocal tries, latency
            tries += 1
            try_started = perf_counter()
            response = await self._client.chat.completions.create(**request)
            latency = perf_counter() - try_started
            return response

        def usage(
            outcome: Outcome,
            response: ChatCompletion | None = None,
            error: Exception | None = None,
            give_up_reason: GiveUpReason | None = None,
        ) -> LLMUsage:
            tokens = response.usage if response is not None else None
            details = tokens.completion_tokens_details if tokens is not None else None
            choice = response.choices[0] if response is not None and response.choices else None
            return LLMUsage(
                time=datetime.now(UTC),
                provider=self.provider,
                model=self.model,
                task=task,
                outcome=outcome,
                tries=tries,
                total_ms=round((perf_counter() - started) * 1000),
                latency_ms=None if latency is None else round(latency * 1000),
                input_tokens=tokens.prompt_tokens if tokens is not None else None,
                output_tokens=tokens.completion_tokens if tokens is not None else None,
                reasoning_tokens=details.reasoning_tokens if details is not None else None,
                finish_reason=safe_code(choice.finish_reason) if choice is not None else None,
                http_status=_http_status(error) if error is not None else None,
                error_code=_error_code(error) if error is not None else None,
                give_up_reason=give_up_reason,
            )

        try:
            retried = await retry_async(
                one_try,
                is_retryable=_is_retryable,
                retry_after=_retry_after,
                describe=_describe,
                policy=self._retry_policy,
                label=f"llm {task}",
                sleep=self._sleep,
                random_fraction=self._random_fraction,
            )
        except RetryGaveUp as gave_up:
            failed = usage("unavailable", error=gave_up.last_error, give_up_reason=gave_up.reason)
            message = (
                f"No answer from {self.provider}: {gave_up.reason} after {gave_up.tries} "
                f"tries, last {_describe(gave_up.last_error)}"
            )
            raise self._recorded(LLMUnavailable(message, failed)) from None
        except openai.APIStatusError as error:  # a 4xx that another try can't fix
            if safe_code(error.code) == JSON_FAILED_CODE:
                failed = usage("invalid_output", error=error)
                problem = OutputProblem("(answer)", JSON_FAILED_CODE)
                message = f"The model could not make valid JSON: {_describe(error)}"
                raise self._recorded(LLMOutputInvalid(message, failed, (problem,))) from None
            failed = usage("refused", error=error)
            message = f"{self.provider} refused the request: {_describe(error)}"
            raise self._recorded(LLMRequestRefused(message, failed)) from None

        response = retried.value
        done = usage("ok", response=response)
        text = response.choices[0].message.content if response.choices else None
        if done.finish_reason == "length":  # cut off: half an answer is not an answer
            failed = done.model_copy(update={"outcome": "invalid_output"})
            problem = OutputProblem("(answer)", "cut_off")
            message = f"The answer was cut off at max_output_tokens={max_output_tokens}"
            raise self._recorded(LLMOutputInvalid(message, failed, (problem,)))
        if not text:
            failed = done.model_copy(update={"outcome": "invalid_output"})
            problem = OutputProblem("(answer)", "empty")
            raise self._recorded(LLMOutputInvalid("The answer was empty", failed, (problem,)))
        return LLMText(text, done)


def make_llm_client(settings: Settings) -> LLMClient:
    """Build the client from .env. Fail fast if LLM_MODEL or the provider's key is missing."""
    info = PROVIDERS[settings.llm_provider]
    settings.require("llm_model", info.key_setting)  # the error names the missing .env line
    api_key: SecretStr = getattr(settings, info.key_setting)
    return LLMClient(
        provider=settings.llm_provider,
        model=str(settings.llm_model),
        api_key=api_key.get_secret_value(),
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        retry_policy=RetryPolicy(deadline_seconds=settings.llm_total_timeout_seconds),
        usage_file=settings.llm_usage_file,
    )
