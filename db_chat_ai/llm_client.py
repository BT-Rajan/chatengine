"""
llm_client.py — same DeepSeek-compatible chat-completions call used by the
original JDK Smart Factory /api/chat endpoint (plain urllib POST with a
Bearer token to <base_url>/v1/chat/completions), pulled out as a small
reusable function so config comes from ai-conf.py instead of a per-app
settings row.
"""

import json
import urllib.request as _req
import urllib.error as _err


class LLMError(RuntimeError):
    pass


def chat_completion(
    messages: list[dict],
    api_key: str,
    model: str,
    base_url: str,
    max_tokens: int = 700,
    temperature: float = 0.2,
    timeout: int = 30,
) -> str:
    """Sends messages to a DeepSeek/OpenAI-compatible /v1/chat/completions
    endpoint and returns the assistant's reply text. Raises LLMError on
    any failure (network, auth, malformed response)."""
    if not api_key:
        raise LLMError(
            "No API key configured. Set DEEPSEEK_API_KEY in ai-conf.py "
            "or as an environment variable."
        )

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    request = _req.Request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    try:
        with _req.urlopen(request, timeout=timeout) as resp:
            result = json.loads(resp.read())
    except _err.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise LLMError(f"AI API returned HTTP {e.code}: {body}") from e
    except _err.URLError as e:
        raise LLMError(f"Could not reach AI API: {e.reason}") from e
    except Exception as e:
        raise LLMError(f"AI request failed: {e}") from e

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"Unexpected AI response shape: {result}") from e
