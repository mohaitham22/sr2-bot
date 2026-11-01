"""Tests for app/services/llm.py (Step 2.4).

No real LLM call, ever (CLAUDE.md section 10): a fake server inside the test (`MockTransport`)
answers instead of Groq or Gemini. The real openai code runs; only the network is fake, so
errors, headers and token counts come out exactly as the SDK reads them. Waits are recorded, not
waited. Fake values only: the name and phone come from tests/conftest.py.
"""

import asyncio
import json
import logging
import time
from pathlib import Path

import httpx2
import pytest
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.services.llm import (
    JSON_FAILED_CODE,
    PROVIDERS,
    ChatMessage,
    LLMClient,
    LLMJson,
    LLMOutputInvalid,
    LLMRequestRefused,
    LLMText,
    LLMUnavailable,
    LLMUsage,
    OutputProblem,
    make_llm_client,
    safe_code,
    strict_json_schema,
)
from app.services.retry import DEFAULT_POLICY, RetryPolicy
from tests.conftest import FAKE_NAME, FAKE_PHONE

FAKE_KEY = "fake-llm-key"
FAKE_MODEL = "fake-model"
USER_TEXT = f"My name is {FAKE_NAME}, phone {FAKE_PHONE}. The kitchen tap leaks."
MESSAGES = [
    ChatMessage(role="system", content="Extract the fields as JSON."),
    ChatMessage(role="user", content=USER_TEXT),
]


class FakeExtraction(BaseModel):
    """A small stand-in for Step 2.8's schema: strict rules (no defaults, no extra keys)."""

    model_config = ConfigDict(extra="forbid")

    unit_number: str | None = Field(pattern=r"^[A-F]-\d{3}$")
    phone: str | None


# --- The fake server ---


def answer(
    content: str | None, finish_reason: str = "stop", reasoning_tokens: int | None = 20
) -> httpx2.Response:
    """A successful chat completion, shaped like Groq's (12 tokens in, 30 out)."""
    details = None if reasoning_tokens is None else {"reasoning_tokens": reasoning_tokens}
    return httpx2.Response(
        200,
        json={
            "id": "fake",
            "object": "chat.completion",
            "created": 1,
            "model": FAKE_MODEL,
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish_reason,
                    "message": {"role": "assistant", "content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 30,
                "total_tokens": 42,
                "completion_tokens_details": details,
            },
        },
    )


def error(
    status: int, code: str | None = None, headers: dict[str, str] | None = None, **extra: str
) -> httpx2.Response:
    """An error answer. Its message holds the user's text, as a provider's message might."""
    body = {"message": f"Problem with: {USER_TEXT}", "type": "fake_error", "code": code, **extra}
    return httpx2.Response(status, headers=headers, json={"error": body})


class FakeServer:
    """Answers from a script, in order, and keeps every request it got.

    A script item is a response, or an httpx2 error class (e.g. httpx2.ReadTimeout) to raise.
    """

    def __init__(self, *script: httpx2.Response | type[Exception]) -> None:
        self.script = list(script)
        self.requests: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, type):
            raise item("fake network problem", request=request)
        return item

    def body(self, number: int = 0) -> dict:
        return json.loads(self.requests[number].content)


def make_client(
    server: FakeServer,
    *,
    provider: str = "groq",
    base_url: str | None = None,
    usage_file: Path | None = None,
    policy: RetryPolicy = DEFAULT_POLICY,
) -> tuple[LLMClient, list[float]]:
    """A client that talks to the fake server; the waits go into the returned list."""
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    client = LLMClient(
        provider=provider,
        model=FAKE_MODEL,
        api_key=FAKE_KEY,
        base_url=base_url,
        retry_policy=policy,
        usage_file=usage_file,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(server.handler)),
        sleep=fake_sleep,
        random_fraction=lambda: 0.5,
    )
    return client, waits


def complete(client: LLMClient) -> LLMText:
    return asyncio.run(client.complete(MESSAGES, temperature=0.7, task="test_text"))


def complete_json(client: LLMClient) -> LLMJson[FakeExtraction]:
    return asyncio.run(
        client.complete_json(MESSAGES, FakeExtraction, temperature=0, task="test_json")
    )


# --- Success ---


def test_complete_sends_the_request_and_returns_text_and_numbers() -> None:
    server = FakeServer(answer("The tap leaks."))
    client, waits = make_client(server)

    result = complete(client)

    body = server.body()
    assert body["model"] == FAKE_MODEL
    assert body["temperature"] == 0.7
    assert body["max_completion_tokens"] == 1024
    assert body["messages"] == [message.model_dump() for message in MESSAGES]
    assert "response_format" not in body  # plain text
    assert result.text == "The tap leaks."
    usage = result.usage
    assert (usage.provider, usage.model, usage.task) == ("groq", FAKE_MODEL, "test_text")
    assert (usage.outcome, usage.tries, usage.finish_reason) == ("ok", 1, "stop")
    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (12, 30, 20)
    assert usage.latency_ms is not None and usage.total_ms >= usage.latency_ms
    assert (usage.http_status, usage.error_code, usage.give_up_reason) == (None, None, None)
    assert waits == []


def test_reasoning_tokens_none_when_the_provider_does_not_say() -> None:
    server = FakeServer(answer("ok", reasoning_tokens=None))
    client, _ = make_client(server)

    assert complete(client).usage.reasoning_tokens is None


def test_complete_json_sends_a_strict_schema_and_returns_checked_data() -> None:
    server = FakeServer(answer('{"unit_number": "B-204", "phone": null}'))
    client, _ = make_client(server)

    result = complete_json(client)

    response_format = server.body()["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "FakeExtraction"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == strict_json_schema(FakeExtraction)
    assert result.data == FakeExtraction(unit_number="B-204", phone=None)
    assert result.usage.outcome == "ok"


@pytest.mark.parametrize("provider", ["groq", "gemini"])
def test_request_goes_to_the_providers_address_with_the_key(provider: str) -> None:
    server = FakeServer(answer("ok"))
    client, _ = make_client(server, provider=provider)

    complete(client)

    url = str(server.requests[0].url)
    assert url == PROVIDERS[provider].base_url.rstrip("/") + "/chat/completions"
    assert server.requests[0].headers["authorization"] == f"Bearer {FAKE_KEY}"


def test_base_url_replaces_the_usual_address() -> None:
    server = FakeServer(answer("ok"))
    client, _ = make_client(server, base_url="https://llm.example.test/v1")

    complete(client)

    assert str(server.requests[0].url) == "https://llm.example.test/v1/chat/completions"


# --- Retries (D3 A) ---


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504])
def test_short_problems_are_retried_with_jitter(status: int) -> None:
    server = FakeServer(error(status), answer("ok"))
    client, waits = make_client(server)

    result = complete(client)

    assert result.usage.tries == 2
    assert waits == [0.5]  # full jitter: 0.5 (the fake random) x min(8, 1 x 2**0)


def test_429_waits_what_the_server_asks() -> None:
    server = FakeServer(error(429, "rate_limit_exceeded", {"retry-after": "3"}), answer("ok"))
    client, waits = make_client(server)

    result = complete(client)

    assert waits == [3.0]
    assert result.usage.tries == 2


@pytest.mark.parametrize("network_error", [httpx2.ReadTimeout, httpx2.ConnectError])
def test_timeout_and_lost_connection_are_retried(network_error: type[Exception]) -> None:
    server = FakeServer(network_error, answer("ok"))
    client, _ = make_client(server)

    assert complete(client).usage.tries == 2


def test_gives_up_after_three_tries() -> None:
    server = FakeServer(error(503), error(503), error(503, "over_capacity"))
    client, waits = make_client(server)

    with pytest.raises(LLMUnavailable, match="max_tries after 3 tries") as raised:
        complete(client)

    usage = raised.value.usage
    assert (usage.outcome, usage.tries, usage.give_up_reason) == ("unavailable", 3, "max_tries")
    assert (raised.value.http_status, raised.value.error_code) == (503, "over_capacity")
    assert usage.latency_ms is None  # no try worked
    assert waits == [0.5, 1.0]


@pytest.mark.parametrize(
    ("network_error", "code"),
    [(httpx2.ReadTimeout, "timeout"), (httpx2.ConnectError, "connection_error")],
)
def test_network_errors_give_our_own_code(network_error: type[Exception], code: str) -> None:
    server = FakeServer(network_error, network_error, network_error)
    client, _ = make_client(server)

    with pytest.raises(LLMUnavailable) as raised:
        complete(client)

    assert (raised.value.http_status, raised.value.error_code) == (None, code)


def test_a_daily_limit_stops_at_once() -> None:
    server = FakeServer(error(429, "rate_limit_exceeded", {"retry-after": "3600"}))
    client, waits = make_client(server)

    with pytest.raises(LLMUnavailable) as raised:
        complete(client)

    assert raised.value.usage.give_up_reason == "retry_after_too_long"
    assert len(server.requests) == 1
    assert waits == []


def test_total_deadline_stops_a_hanging_request() -> None:
    """Real time (0.05 s): the server never answers; the deadline stops the call (change 1)."""

    async def hangs(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(5)
        return answer("too late")

    client = LLMClient(
        provider="groq",
        model=FAKE_MODEL,
        api_key=FAKE_KEY,
        retry_policy=RetryPolicy(deadline_seconds=0.05),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(hangs)),
    )
    start = time.monotonic()

    with pytest.raises(LLMUnavailable) as raised:
        complete(client)

    assert time.monotonic() - start < 1.0
    usage = raised.value.usage
    assert (usage.give_up_reason, usage.error_code, usage.tries) == ("deadline", "timeout", 1)


def test_per_try_timeout_and_total_deadline_on_a_real_connection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Real HTTP on this machine (no internet), like the Gemini call of 2026-10-31: a server
    that takes the request and never answers. The fake server above can't show the per-try
    timeout (the real network layer enforces it), so this test uses a real local socket.
    Per try 0.3 s, total 0.5 s: try 1 is stopped by the per-try timeout and retried; try 2
    gets only what is left, so the call ends at the deadline (~0.5 s). Without the deadline
    timer, try 2 would run its whole 0.3 s (~0.75 s): the bound below catches that (found by
    breaking the timer on purpose; a first version with "< 1.5 s" didn't).
    The number of tries is not checked: a real "0.3 s" try takes a little longer (connection,
    a ~16 ms clock on Windows), so on a slow machine no time may be left for try 2 (also right)."""
    caplog.set_level(logging.WARNING)

    async def scenario() -> tuple[LLMUnavailable, float]:
        async def never_answers(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.read(65536)  # take the request ...
            await asyncio.Event().wait()  # ... and say nothing (cancelled when the test ends)

        server = await asyncio.start_server(never_answers, "127.0.0.1", 0)  # 0 = any free port
        port = server.sockets[0].getsockname()[1]
        client = LLMClient(
            provider="groq",
            model=FAKE_MODEL,
            api_key=FAKE_KEY,
            base_url=f"http://127.0.0.1:{port}/v1",
            timeout_seconds=0.3,
            retry_policy=RetryPolicy(base_seconds=0.01, deadline_seconds=0.5),
        )
        start = time.monotonic()
        try:
            await client.complete(MESSAGES, temperature=0, task="test_text")
        except LLMUnavailable as error:
            return error, time.monotonic() - start
        finally:
            await client.close()
            server.close()
        raise AssertionError("the call should have failed")

    error, seconds = asyncio.run(scenario())

    assert "timeout on try 1 of 3" in caplog.text  # the per-try timeout fired first
    assert (error.usage.give_up_reason, error.error_code) == ("deadline", "timeout")
    # Ended AT the deadline (0.5 s), not after try 2's whole 0.3 s (~0.75 s): what the user waits
    assert 0.45 <= seconds < 0.65
    assert error.usage.total_ms < 650


# --- Refused and invalid (change 7) ---


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "invalid_api_key"), (404, "model_not_found"), (400, "invalid_request"), (413, None)],
)
def test_request_refused_is_not_retried_and_keeps_status_and_code(
    status: int, code: str | None
) -> None:
    server = FakeServer(error(status, code))
    client, waits = make_client(server)

    with pytest.raises(LLMRequestRefused) as raised:
        complete(client)

    assert (raised.value.http_status, raised.value.error_code) == (status, code)
    assert raised.value.usage.outcome == "refused"
    assert len(server.requests) == 1
    assert waits == []


def test_groq_json_validate_failed_is_invalid_output_not_refused() -> None:
    """Groq: HTTP 400 when the model can't make valid JSON. Its body has the failed answer."""
    server = FakeServer(error(400, JSON_FAILED_CODE, failed_generation=f'{{"phone": "{FAKE_PHONE}'))
    client, waits = make_client(server)

    with pytest.raises(LLMOutputInvalid) as raised:
        complete_json(client)

    assert raised.value.problems == (OutputProblem("(answer)", JSON_FAILED_CODE),)
    assert (raised.value.http_status, raised.value.error_code) == (400, JSON_FAILED_CODE)
    assert raised.value.usage.outcome == "invalid_output"
    assert len(server.requests) == 1  # no retry here: Step 2.9 re-asks with the problems
    assert waits == []


def test_answer_that_does_not_fit_lists_fields_and_kinds_never_values() -> None:
    # The phone where the unit belongs (breaks the pattern), and no "phone" key at all
    server = FakeServer(answer(json.dumps({"unit_number": FAKE_PHONE})))
    client, _ = make_client(server)

    with pytest.raises(LLMOutputInvalid) as raised:
        complete_json(client)

    assert set(raised.value.problems) == {
        OutputProblem("unit_number", "string_pattern_mismatch"),
        OutputProblem("phone", "missing"),
    }
    assert FAKE_PHONE not in str(raised.value)
    assert raised.value.usage.input_tokens == 12  # the numbers of the call are kept


def test_broken_json_is_invalid_output() -> None:
    server = FakeServer(answer('{"unit_number": '))
    client, _ = make_client(server)

    with pytest.raises(LLMOutputInvalid) as raised:
        complete_json(client)

    assert raised.value.problems == (OutputProblem("(answer)", "json_invalid"),)


def test_cut_off_answer_is_invalid_output_with_its_numbers() -> None:
    server = FakeServer(answer('{"unit_n', finish_reason="length"))
    client, _ = make_client(server)

    with pytest.raises(LLMOutputInvalid, match="cut off") as raised:
        complete(client)

    usage = raised.value.usage
    assert raised.value.problems == (OutputProblem("(answer)", "cut_off"),)
    assert (usage.finish_reason, usage.output_tokens, usage.reasoning_tokens) == ("length", 30, 20)


def test_empty_answer_is_invalid_output() -> None:
    server = FakeServer(answer(None))
    client, _ = make_client(server)

    with pytest.raises(LLMOutputInvalid) as raised:
        complete(client)

    assert raised.value.problems == (OutputProblem("(answer)", "empty"),)


def test_our_errors_never_chain_the_providers_error() -> None:
    server = FakeServer(error(401, "invalid_api_key"))
    client, _ = make_client(server)

    with pytest.raises(LLMRequestRefused) as raised:
        complete(client)

    assert raised.value.__cause__ is None
    assert raised.value.__suppress_context__ is True  # a traceback won't print the SDK's error
    assert USER_TEXT not in str(raised.value)


# --- Checks before sending ---


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"messages": []}, "messages"),
        ({"temperature": 2.5}, "temperature"),
        ({"temperature": -0.1}, "temperature"),
        ({"max_output_tokens": 0}, "max_output_tokens"),
        ({"task": "extract the phone"}, "task"),  # a sentence, not a label
    ],
)
def test_wrong_arguments_fail_before_sending(changes: dict, message: str) -> None:
    server = FakeServer()
    client, _ = make_client(server)
    arguments = {"messages": MESSAGES, "temperature": 0.0, "task": "test_text"} | changes

    with pytest.raises(ValueError, match=message):
        asyncio.run(client.complete(**arguments))

    assert server.requests == []


def test_schema_against_the_strict_rules_fails_before_sending() -> None:
    class HasDefault(BaseModel):
        model_config = ConfigDict(extra="forbid")
        phone: str | None = None

    server = FakeServer()
    client, _ = make_client(server)

    with pytest.raises(TypeError, match=r"every field required.*phone"):
        asyncio.run(client.complete_json(MESSAGES, HasDefault, temperature=0, task="test_json"))

    assert server.requests == []


def test_strict_json_schema_checks_nested_models() -> None:
    class LooseUnit(BaseModel):  # no extra="forbid"
        building: str | None

    class WithUnit(BaseModel):
        model_config = ConfigDict(extra="forbid")
        unit: LooseUnit

    assert strict_json_schema(FakeExtraction)["additionalProperties"] is False
    with pytest.raises(TypeError, match="LooseUnit: strict mode needs model_config extra='forbid'"):
        strict_json_schema(WithUnit)


@pytest.mark.parametrize(
    ("value", "kept"),
    [
        ("invalid_api_key", "invalid_api_key"),
        ("INVALID_ARGUMENT", "INVALID_ARGUMENT"),
        (400, "400"),
        ("unit.building", "unit.building"),
        (f"phone {FAKE_PHONE}", "other"),  # a space or "+": not a code
        ("x" * 65, "other"),
        (None, None),
    ],
)
def test_safe_code_keeps_only_codes(value: object, kept: str | None) -> None:
    assert safe_code(value) == kept


# --- Privacy: the text never leaves through logs, errors or the usage file ---


def test_logs_never_hold_the_messages_or_the_answer(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)  # every logger, the openai SDK's and httpx2's included
    server = FakeServer(
        error(503),
        answer(json.dumps({"unit_number": "B-204", "phone": FAKE_PHONE})),
        error(400, JSON_FAILED_CODE, failed_generation=FAKE_PHONE),
    )
    client, _ = make_client(server)

    complete_json(client)
    with pytest.raises(LLMOutputInvalid):
        complete_json(client)

    assert "llm test_json: ok" in caplog.text  # the numbers are logged ...
    for secret in (FAKE_NAME, FAKE_PHONE, "kitchen tap", "Extract the fields", FAKE_KEY):
        assert secret not in caplog.text  # ... the text and the key never


def test_printed_results_and_messages_hide_the_text() -> None:
    server = FakeServer(answer(f"Call {FAKE_PHONE}"))
    client, _ = make_client(server)

    result = complete(client)

    printed = repr(result) + str(result) + repr(MESSAGES) + str(MESSAGES)
    assert FAKE_PHONE not in printed
    assert FAKE_NAME not in printed


def test_usage_file_gets_one_line_per_call_with_numbers_only(tmp_path: Path) -> None:
    usage_file = tmp_path / "llm_usage" / "usage.jsonl"  # the folder is made when needed
    server = FakeServer(
        answer(json.dumps({"unit_number": "B-204", "phone": FAKE_PHONE})),
        error(401, "invalid_api_key"),
    )
    client, _ = make_client(server, usage_file=usage_file)

    complete_json(client)
    with pytest.raises(LLMRequestRefused):
        complete(client)

    text = usage_file.read_text(encoding="utf-8")
    lines = [json.loads(line) for line in text.splitlines()]
    assert [line["outcome"] for line in lines] == ["ok", "refused"]
    assert all(set(line) == set(LLMUsage.model_fields) for line in lines)
    for secret in (FAKE_NAME, FAKE_PHONE, "kitchen tap", FAKE_KEY):
        assert secret not in text


def test_usage_file_problem_does_not_break_the_call(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    server = FakeServer(answer("ok"))
    client, _ = make_client(server, usage_file=tmp_path)  # a folder: it can't be opened as a file

    result = complete(client)

    assert result.text == "ok"
    assert "Could not write the LLM usage file" in caplog.text


def test_usage_record_refuses_text_as_a_task() -> None:
    with pytest.raises(ValueError):
        LLMUsage.model_validate(
            {
                "time": "2026-10-31T12:00:00Z",
                "provider": "groq",
                "model": FAKE_MODEL,
                "task": USER_TEXT,
                "outcome": "ok",
                "tries": 1,
                "total_ms": 1,
                "latency_ms": 1,
                "input_tokens": 1,
                "output_tokens": 1,
                "reasoning_tokens": None,
                "finish_reason": "stop",
                "http_status": None,
                "error_code": None,
                "give_up_reason": None,
            }
        )


def test_list_models_returns_sorted_names() -> None:
    models = [{"id": name, "object": "model", "created": 1, "owned_by": "fake"} for name in "ba"]
    server = FakeServer(httpx2.Response(200, json={"object": "list", "data": models}))
    client, _ = make_client(server)

    names = asyncio.run(client.list_models())

    assert names == ["a", "b"]
    assert str(server.requests[0].url).endswith("/models")


# --- make_llm_client: settings from .env ---

LLM_ENV_NAMES = ["GROQ_API_KEY", "GEMINI_API_KEY", "LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL"]


@pytest.fixture
def no_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start like CI: none of our LLM variables in the environment."""
    for name in LLM_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.usefixtures("no_llm_env")
def test_make_llm_client_uses_the_providers_own_key() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_model="fake-gemini-model",
        gemini_api_key="fake-gemini-key",
    )

    client = make_llm_client(settings)

    assert (client.provider, client.model) == ("gemini", "fake-gemini-model")


@pytest.mark.usefixtures("no_llm_env")
@pytest.mark.parametrize(
    ("values", "missing"),
    [
        ({"groq_api_key": "fake-groq-key"}, "LLM_MODEL"),
        ({"llm_model": FAKE_MODEL}, "GROQ_API_KEY"),
        # Gemini chosen, but only the Groq key is set
        (
            {"llm_provider": "gemini", "llm_model": FAKE_MODEL, "groq_api_key": "k"},
            "GEMINI_API_KEY",
        ),
    ],
)
def test_make_llm_client_names_the_missing_env_line(values: dict, missing: str) -> None:
    settings = Settings(_env_file=None, **values)

    with pytest.raises(RuntimeError, match=missing):
        make_llm_client(settings)
