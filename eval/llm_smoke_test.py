"""Step 2.4 manual check: ONE real LLM call with a harmless sentence. Never run in CI.

    uv run python -m eval.llm_smoke_test                       # the provider and model in .env
    uv run python -m eval.llm_smoke_test --list-models         # names your key may use (no tokens)
    uv run python -m eval.llm_smoke_test --provider gemini --list-models
    uv run python -m eval.llm_smoke_test --provider gemini --model <name>
    uv run python -m eval.llm_smoke_test --text                # plain text: no schema at all

The sentence is our own and holds no personal data, so this script may print the answer; the app
never does. The numbers also go to LLM_USAGE_FILE (if set), like every call through llm.py.
"""

import argparse
import asyncio
import logging
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

from app.config import LLMProvider, get_settings
from app.logging_setup import setup_logging
from app.services.llm import ChatMessage, LLMError, make_llm_client

logger = logging.getLogger("eval.llm_smoke_test")  # fixed name: with -m, __name__ is __main__

SENTENCE = "The weather in Cairo is sunny today."
MESSAGES = [
    ChatMessage(
        role="system",
        content="Describe the user's sentence. Answer only with the JSON object of the schema.",
    ),
    ChatMessage(role="user", content=SENTENCE),
]
# --text: the same sentence, but a plain-text answer (complete(), no response_format). Shows
# whether a problem comes from the JSON schema or from the model itself
TEXT_MESSAGES = [
    ChatMessage(role="system", content="Describe the user's sentence in at most 5 words."),
    ChatMessage(role="user", content=SENTENCE),
]


class SmokeAnswer(BaseModel):
    """Three simple facts about the sentence, in the strict-mode shape (no defaults)."""

    model_config = ConfigDict(extra="forbid")

    language: Literal["ar", "en"]
    word_count: int
    summary: str = Field(description="The sentence in at most 5 words")


async def run(provider: str | None, model: str | None, list_models: bool, text: bool) -> int:
    """Return the exit code: 0 = it worked, 1 = an LLM error (its type and codes are logged)."""
    settings = get_settings()
    changes = {"llm_provider": provider, "llm_model": model}
    settings = settings.model_copy(update={k: v for k, v in changes.items() if v is not None})
    client = make_llm_client(settings)  # fails fast if the model or the key is missing
    try:
        if list_models:
            for name in await client.list_models():
                print(name)
            return 0
        if text:
            text_result = await client.complete(TEXT_MESSAGES, temperature=0, task="smoke_test")
            answer, usage = text_result.text, text_result.usage
        else:
            result = await client.complete_json(
                MESSAGES, SmokeAnswer, temperature=0, task="smoke_test"
            )
            answer, usage = result.data.model_dump(), result.usage
    except LLMError as error:
        logger.error("%s: %s", type(error).__name__, error)
        return 1
    finally:
        await client.close()

    print(f"Provider: {usage.provider} | model: {usage.model} | {'text' if text else 'JSON'}")
    print(f"Sentence: {SENTENCE}")
    print(f"Answer:   {answer!r}")
    print(
        f"Numbers:  tries={usage.tries} total_ms={usage.total_ms} latency_ms={usage.latency_ms} "
        f"tokens in={usage.input_tokens} out={usage.output_tokens} "
        f"reasoning={usage.reasoning_tokens} finish={usage.finish_reason}"
    )
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Step 2.4: one real LLM call (harmless text).")
    parser.add_argument("--provider", choices=get_args(LLMProvider), help="instead of .env")
    parser.add_argument("--model", help="instead of LLM_MODEL in .env")
    parser.add_argument("--list-models", action="store_true", help="list model names, no call")
    parser.add_argument("--text", action="store_true", help="plain text, no JSON schema")
    args = parser.parse_args()

    settings = get_settings()
    keys = [settings.groq_api_key, settings.gemini_api_key]
    # Each key becomes *** if any log line ever contains it
    setup_logging(secrets=[key.get_secret_value() for key in keys if key is not None])
    # The HTTP library logs every request at INFO: no secrets or text, just noise
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    raise SystemExit(asyncio.run(run(args.provider, args.model, args.list_models, args.text)))


if __name__ == "__main__":
    main()
