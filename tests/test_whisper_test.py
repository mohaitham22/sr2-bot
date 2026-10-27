"""Tests for eval/whisper_test.py. Fakes only: no Whisper model, no network, no Groq quota."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import groq
import httpx
import pytest
from groq.types.audio import Transcription

from eval.whisper_test import (
    LOCAL_ENGINE,
    ResultRow,
    append_row,
    done_keys,
    pending,
    transcribe_groq,
    transcribe_local,
    with_retry,
)

FAKE_REQUEST = httpx.Request("POST", "https://api.groq.com/fake")


def make_error(status: int, headers: dict[str, str] | None = None) -> groq.APIStatusError:
    """A real groq error object (429 or 401), built from a fake HTTP response."""
    response = httpx.Response(status, headers=headers, request=FAKE_REQUEST)
    error_class = groq.RateLimitError if status == 429 else groq.AuthenticationError
    return error_class("fake error", response=response, body=None)


class FakeCall:
    """Raises the given errors one by one, then returns "ok". Counts the calls."""

    def __init__(self, errors: list[Exception]) -> None:
        self.errors = errors
        self.calls = 0

    def __call__(self) -> str:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


# --- with_retry: the 429 rule (D8 A). A fake sleep records the waits instead of waiting ---


def test_retry_waits_retry_after_then_succeeds() -> None:
    call = FakeCall([make_error(429, {"retry-after": "3"})])
    waits: list[float] = []

    assert with_retry(call, sleep=waits.append) == "ok"
    assert waits == [3.0]
    assert call.calls == 2


def test_retry_uses_backoff_without_header() -> None:
    call = FakeCall([make_error(429), make_error(429)])
    waits: list[float] = []

    assert with_retry(call, sleep=waits.append) == "ok"
    assert waits == [2.0, 4.0]


def test_retry_gives_up_after_max_tries() -> None:
    call = FakeCall([make_error(429) for _ in range(10)])
    waits: list[float] = []

    with pytest.raises(groq.RateLimitError):
        with_retry(call, max_tries=5, sleep=waits.append)
    assert call.calls == 5
    assert waits == [2.0, 4.0, 8.0, 16.0]


def test_other_errors_are_not_retried() -> None:
    call = FakeCall([make_error(401)])  # wrong key: waiting can't fix it
    waits: list[float] = []

    with pytest.raises(groq.AuthenticationError):
        with_retry(call, sleep=waits.append)
    assert call.calls == 1
    assert waits == []


# --- results.csv: one row at a time, and resume ---


def make_row(file: str, setting: str, transcript: str = "fake text") -> ResultRow:
    return ResultRow(
        file=file,
        engine=LOCAL_ENGINE,
        model="small",
        language_setting=setting,
        detected_language="ar",
        language_probability=0.9,
        audio_seconds=10.0,
        seconds=2.0,
        rtf=0.2,
        transcript=transcript,
    )


def test_rows_are_appended_and_skipped_on_resume(tmp_path: Path) -> None:
    results = tmp_path / "results.csv"
    arabic = "الحنفية بتنقط في الحمام"  # fake text

    assert done_keys(results) == set()  # no file yet
    append_row(results, make_row("a.ogg", "auto", arabic))
    append_row(results, make_row("a.ogg", "set"))

    lines = results.read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("file,engine,model") for line in lines) == 1  # header once
    assert arabic in lines[1]
    files = [tmp_path / "a.ogg", tmp_path / "b.ogg"]
    done = done_keys(results)
    assert pending(files, LOCAL_ENGINE, "small", done) == [(files[1], "auto"), (files[1], "set")]
    assert len(pending(files, LOCAL_ENGINE, "medium", done)) == 4  # other model: all to do


# --- transcribe_groq with a fake client ---


class FakeTranscriptions:
    """Stands in for client.audio.transcriptions. Records what it was called with."""

    def __init__(self, result: Transcription) -> None:
        self.result = result
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Transcription:
        self.kwargs = kwargs
        return self.result


@pytest.mark.parametrize(("setting", "sent"), [("auto", groq.NOT_GIVEN), ("set", "ar")])
def test_transcribe_groq(tmp_path: Path, setting: str, sent: object) -> None:
    audio = tmp_path / "note.ogg"
    audio.write_bytes(b"fake audio")
    result = Transcription(text=" fake text ", language="Arabic", duration=4.0)
    transcriptions = FakeTranscriptions(result)
    client: Any = SimpleNamespace(audio=SimpleNamespace(transcriptions=transcriptions))

    row = transcribe_groq(client, audio, setting, "ar")

    assert transcriptions.kwargs["language"] == sent  # auto: no language is sent at all
    assert transcriptions.kwargs["file"] == ("note.ogg", b"fake audio")
    assert row.detected_language == "ar"  # "Arabic" -> "ar", like faster-whisper
    assert row.language_probability is None
    assert row.transcript == "fake text"
    assert row.audio_seconds == 4.0
    assert row.rtf == pytest.approx(row.seconds / 4.0, abs=0.01)


# --- transcribe_local with a fake model ---


class FakeWhisperModel:
    """Stands in for faster_whisper.WhisperModel. Records the language it was given."""

    def __init__(self) -> None:
        self.language: str | None = "not called"

    def transcribe(self, audio: str, language: str | None = None) -> tuple[Any, Any]:
        self.language = language
        info = SimpleNamespace(
            language=language or "ar",
            language_probability=0.876543 if language is None else 1.0,
            duration=10.0,
        )
        segments = (SimpleNamespace(text=text) for text in [" first part ", " second part "])
        return segments, info


@pytest.mark.parametrize(("setting", "passed"), [("auto", None), ("set", "ar")])
def test_transcribe_local(setting: str, passed: str | None) -> None:
    model: Any = FakeWhisperModel()

    row = transcribe_local(model, "small", Path("note.ogg"), setting, "ar")

    assert model.language == passed  # auto: language=None, so Whisper detects it
    assert row.transcript == "first part second part"
    assert row.audio_seconds == 10.0
    assert row.language_probability == (0.877 if setting == "auto" else 1.0)
    assert row.rtf == pytest.approx(row.seconds / 10.0, abs=0.01)
