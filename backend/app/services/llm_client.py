"""
LLM client for the Groq / OpenAI-compatible chat completions API.

Provides:
    1. stream_chat_completion() -> normal chatbot streaming
    2. chat_completion()        -> small non-streaming calls such as
                                   follow-up question rewriting
"""

import json
import logging
from typing import Dict, Generator, List, Optional

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


HEADERS = {
    "Authorization": f"Bearer {settings.LLM_API_KEY}",
    "Content-Type": "application/json",
}


# ============================================================
# STREAMING CHAT COMPLETION
# ============================================================

def stream_chat_completion(
    messages: List[Dict],
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> Generator[str, None, None]:

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }

    try:

        with requests.post(
            settings.LLM_API_URL,
            headers=HEADERS,
            json=payload,
            stream=True,
            timeout=(
                settings.LLM_REQUEST_TIMEOUT_CONNECT,
                settings.LLM_REQUEST_TIMEOUT_READ,
            ),
        ) as r:

            if r.status_code != 200:

                logger.error(
                    "LLM API error %s: %s",
                    r.status_code,
                    r.text[:500],
                )

                yield (
                    "Sorry — the assistant is temporarily "
                    "unavailable. Please try again shortly."
                )

                return

            for line in r.iter_lines():

                if not line:
                    continue

                decoded = line.decode(
                    "utf-8"
                ).strip()

                if not decoded.startswith("data:"):
                    continue

                chunk = (
                    decoded
                    .removeprefix("data:")
                    .strip()
                )

                if chunk == "[DONE]":
                    break

                try:

                    data = json.loads(
                        chunk
                    )

                    delta = (
                        data["choices"][0]["delta"]
                        .get("content")
                    )

                    if delta:
                        yield delta

                except (
                    KeyError,
                    IndexError,
                    json.JSONDecodeError,
                ):
                    continue

    except requests.exceptions.Timeout:

        yield (
            "The request timed out. "
            "Please try again."
        )

    except requests.exceptions.RequestException:

        logger.exception(
            "Network error contacting LLM API"
        )

        yield (
            "A network error occurred "
            "while contacting the assistant."
        )


# ============================================================
# NON-STREAMING CHAT COMPLETION
# ============================================================

def chat_completion(
    messages: List[Dict],
    max_tokens: int = 150,
    temperature: float = 0.0,
) -> Optional[str]:
    """
    Small non-streaming LLM request.

    Used for internal tasks such as:
        - rewriting follow-up questions
        - converting a contextual question into a
          standalone retrieval query

    This function intentionally uses a small token limit
    to reduce API usage.
    """

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }

    try:

        response = requests.post(
            settings.LLM_API_URL,
            headers=HEADERS,
            json=payload,
            timeout=(
                settings.LLM_REQUEST_TIMEOUT_CONNECT,
                settings.LLM_REQUEST_TIMEOUT_READ,
            ),
        )

        if response.status_code != 200:

            logger.error(
                "LLM non-streaming API error %s: %s",
                response.status_code,
                response.text[:500],
            )

            return None

        data = response.json()

        content = (
            data["choices"][0]["message"]
            .get("content")
        )

        if not content:
            return None

        return content.strip()

    except requests.exceptions.Timeout:

        logger.warning(
            "LLM non-streaming request timed out."
        )

        return None

    except (
        requests.exceptions.RequestException,
        KeyError,
        IndexError,
        ValueError,
        json.JSONDecodeError,
    ):

        logger.exception(
            "Non-streaming LLM request failed."
        )

        return None