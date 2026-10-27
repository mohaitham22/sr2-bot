"""Step 1.6: transcribe the test voice notes with several Whisper models and save the results.

Run:  uv run python -m eval.whisper_test                  (everything: local models, then Groq)
      uv run python -m eval.whisper_test --engine local --models small   (e.g. a quick trial)
      uv run python -m eval.whisper_test --engine groq    (only the Groq comparison)

Each transcript becomes one row in eval/voice/results.csv, written at once. Rows that already
exist are skipped, so the script can stop and continue later. Transcripts go only to that file,
never to the logs: they count as personal data (CLAUDE.md section 9).

Groq is a comparison only, never used in the app (CLAUDE.md section 13). Only our own test
recordings with fake data may be sent to it.
"""

import argparse
import csv
import logging
import time
from collections.abc import Callable
from pathlib import Path

import groq
from faster_whisper import WhisperModel
from groq.types.audio import Transcription
from pydantic import BaseModel

from app.config import ROOT_DIR, get_settings
from app.logging_setup import setup_logging

logger = logging.getLogger("eval.whisper_test")

VOICE_DIR = ROOT_DIR / "eval" / "voice"
RAW_DIR = VOICE_DIR / "raw"
REFERENCE_CSV = VOICE_DIR / "reference.csv"
RESULTS_CSV = VOICE_DIR / "results.csv"

# The test matrix: every model x every language setting. Fixed on purpose, not read from .env
LOCAL_MODELS = ["small", "medium", "large-v3", "large-v3-turbo"]
LANGUAGE_SETTINGS = ["auto", "set"]  # auto = Whisper guesses; set = language from reference.csv
LOCAL_ENGINE = "faster-whisper"
COMPUTE_TYPE = "int8"
CPU_THREADS = 4  # D6 A: like the free server (up to 4 cores), not all 8 laptop cores

GROQ_ENGINE = "groq"
GROQ_MODEL = "whisper-large-v3"
GROQ_TIMEOUT_SECONDS = 60
MAX_TRIES = 5  # for HTTP 429: the first try + 4 retries
# verbose_json names the language in words; we store the short code, like faster-whisper does
LANGUAGE_CODES = {"arabic": "ar", "english": "en"}

RowKey = tuple[str, str, str, str]  # (file, engine, model, language_setting)


class ResultRow(BaseModel):
    """One transcript: one file, by one model, with one language setting."""

    file: str
    engine: str
    model: str
    language_setting: str
    detected_language: str  # with "set", this is simply the language we gave
    language_probability: float | None  # how sure Whisper was (1.0 with "set"; Groq: none)
    audio_seconds: float
    seconds: float  # time to transcribe; loading the model and 429 waits are not included
    rtf: float  # real-time factor = seconds / audio_seconds
    transcript: str

    def key(self) -> RowKey:
        return (self.file, self.engine, self.model, self.language_setting)


def load_languages(reference_csv: Path) -> dict[str, str]:
    """Map each voice file name to its language ("ar" or "en"), from reference.csv."""
    with reference_csv.open(encoding="utf-8", newline="") as f:
        return {row["file_name"]: row["language"] for row in csv.DictReader(f)}


def done_keys(results_csv: Path) -> set[RowKey]:
    """Keys of the rows already in results.csv, so we don't do them again."""
    if not results_csv.exists():
        return set()
    with results_csv.open(encoding="utf-8", newline="") as f:
        return {
            (row["file"], row["engine"], row["model"], row["language_setting"])
            for row in csv.DictReader(f)
        }


def pending(
    files: list[Path], engine: str, model: str, done: set[RowKey]
) -> list[tuple[Path, str]]:
    """The (file, language setting) pairs that this engine and model still have to do."""
    return [
        (audio, setting)
        for audio in files
        for setting in LANGUAGE_SETTINGS
        if (audio.name, engine, model, setting) not in done
    ]


def append_row(results_csv: Path, row: ResultRow) -> None:
    """Add one row now, so a crash or Ctrl+C keeps all finished rows."""
    is_new = not results_csv.exists()
    with results_csv.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ResultRow.model_fields))
        if is_new:
            writer.writeheader()
        writer.writerow(row.model_dump())


def log_row(row: ResultRow, number: int, total: int) -> None:
    """Log the numbers of one row. Never the transcript."""
    logger.info(
        "%s %d/%d %s %s: audio %.1f s, took %.1f s, RTF %.2f, language %s (%s)",
        row.model,
        number,
        total,
        row.file,
        row.language_setting,
        row.audio_seconds,
        row.seconds,
        row.rtf,
        row.detected_language,
        "-" if row.language_probability is None else f"{row.language_probability:.2f}",
    )


# --- Self-hosted: faster-whisper on the CPU ---


def transcribe_local(
    model: WhisperModel, model_name: str, audio: Path, setting: str, language: str
) -> ResultRow:
    """Transcribe one file. With setting "auto", Whisper detects the language itself."""
    start = time.perf_counter()
    segments, info = model.transcribe(str(audio), language=None if setting == "auto" else language)
    # `segments` is a lazy generator: the decoding happens while we read it, so the clock
    # must stop only after this line
    text = " ".join(segment.text.strip() for segment in segments)
    seconds = time.perf_counter() - start
    return ResultRow(
        file=audio.name,
        engine=LOCAL_ENGINE,
        model=model_name,
        language_setting=setting,
        detected_language=info.language,
        language_probability=round(info.language_probability, 3),
        audio_seconds=round(info.duration, 2),
        seconds=round(seconds, 2),
        rtf=round(seconds / info.duration, 3),
        transcript=text,
    )


def run_local(
    model_names: list[str],
    files: list[Path],
    languages: dict[str, str],
    model_dir: Path | None,
    results_csv: Path,
) -> None:
    """Load each model once, then transcribe every file with every language setting."""
    done = done_keys(results_csv)
    for model_name in model_names:
        todo = pending(files, LOCAL_ENGINE, model_name, done)
        if not todo:
            logger.info("%s: all rows already in results.csv, skipped", model_name)
            continue

        logger.info("%s: loading (the first time, this includes the download)", model_name)
        start = time.perf_counter()
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type=COMPUTE_TYPE,
            cpu_threads=CPU_THREADS,
            download_root=str(model_dir) if model_dir else None,
        )
        logger.info("%s: loaded in %.1f s", model_name, time.perf_counter() - start)

        # Warm-up: the first run after loading is slower than the rest. It is not saved
        transcribe_local(model, model_name, files[0], "set", languages[files[0].name])

        for number, (audio, setting) in enumerate(todo, start=1):
            row = transcribe_local(model, model_name, audio, setting, languages[audio.name])
            append_row(results_csv, row)
            log_row(row, number, len(todo))
        del model  # free the memory before loading the next model


# --- Cloud comparison: Groq API ---


def retry_after_seconds(error: groq.RateLimitError) -> float | None:
    """The wait the server asks for in its retry-after header, if it sent a number."""
    value = error.response.headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except ValueError:  # retry-after can also be a date; then we use our own backoff
        return None


def with_retry[T](
    call: Callable[[], T],
    max_tries: int = MAX_TRIES,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Run `call`. On HTTP 429, wait and try again (D8 A).

    The wait is the server's retry-after, or else exponential backoff: 2, 4, 8, 16 s.
    `sleep` is a parameter so tests can pass a fake one and never really wait.
    """
    for attempt in range(1, max_tries):
        try:
            return call()
        except groq.RateLimitError as error:
            wait = retry_after_seconds(error) or 2.0**attempt
            logger.warning(
                "HTTP 429 rate limit: waiting %.1f s (try %d of %d)", wait, attempt, max_tries
            )
            sleep(wait)
    return call()  # the last try: a 429 now goes up to the caller and stops the script


def transcribe_groq(client: groq.Groq, audio: Path, setting: str, language: str) -> ResultRow:
    """Transcribe one file with the Groq API. With setting "auto", no language is sent."""

    def call() -> tuple[Transcription, float]:
        start = time.perf_counter()
        result = client.audio.transcriptions.create(
            file=(audio.name, audio.read_bytes()),
            model=GROQ_MODEL,
            language=groq.NOT_GIVEN if setting == "auto" else language,
            response_format="verbose_json",  # also returns the language and the duration
        )
        # Time only the try that worked: the waits after a 429 are not Groq's speed
        return result, time.perf_counter() - start

    result, seconds = with_retry(call)
    detected = str(result.language)  # verbose_json fields are extra fields on Transcription
    duration = float(result.duration)
    return ResultRow(
        file=audio.name,
        engine=GROQ_ENGINE,
        model=GROQ_MODEL,
        language_setting=setting,
        detected_language=LANGUAGE_CODES.get(detected.lower(), detected),
        language_probability=None,
        audio_seconds=round(duration, 2),
        seconds=round(seconds, 2),
        rtf=round(seconds / duration, 3),
        transcript=result.text.strip(),
    )


def run_groq(
    client: groq.Groq, files: list[Path], languages: dict[str, str], results_csv: Path
) -> None:
    """Send every file to Groq, with every language setting."""
    todo = pending(files, GROQ_ENGINE, GROQ_MODEL, done_keys(results_csv))
    if not todo:
        logger.info("%s: all rows already in results.csv, skipped", GROQ_MODEL)
        return
    for number, (audio, setting) in enumerate(todo, start=1):
        row = transcribe_groq(client, audio, setting, languages[audio.name])
        append_row(results_csv, row)
        log_row(row, number, len(todo))


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 1.6: Whisper test on the voice notes.")
    parser.add_argument(
        "--engine", choices=["local", "groq", "all"], default="all", help="engines to run"
    )
    parser.add_argument(
        "--models", nargs="+", choices=LOCAL_MODELS, default=LOCAL_MODELS, help="local models"
    )
    args = parser.parse_args()
    use_local = args.engine in ("local", "all")
    use_groq = args.engine in ("groq", "all")

    settings = get_settings()
    if use_groq:
        settings.require("groq_api_key")  # fail fast, before any work
    groq_key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    setup_logging(secrets=[groq_key])  # the key becomes *** if any log line ever contains it
    # The HTTP libraries log every request at INFO: no secrets, just noise. Keep their warnings
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Fail fast: every voice file needs a row (and a language) in reference.csv
    files = sorted(RAW_DIR.glob("*.ogg"))
    languages = load_languages(REFERENCE_CSV)
    missing = [audio.name for audio in files if audio.name not in languages]
    if not files or missing:
        raise SystemExit(f"No voice files, or not in reference.csv: {missing or RAW_DIR}")

    if use_local:
        if settings.stt_model_dir is None:
            logger.warning("STT_MODEL_DIR is not set: models go to Hugging Face's cache on C:")
        run_local(args.models, files, languages, settings.stt_model_dir, RESULTS_CSV)
    if use_groq:
        # max_retries=0: the SDK's own hidden retry is off; with_retry() does it (D8 A)
        client = groq.Groq(api_key=groq_key, max_retries=0, timeout=GROQ_TIMEOUT_SECONDS)
        run_groq(client, files, languages, RESULTS_CSV)
    logger.info("Done. Results in %s", RESULTS_CSV.relative_to(ROOT_DIR))


if __name__ == "__main__":
    main()
