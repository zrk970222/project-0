"""Streaming demo for GET /v1/stream (Day 4, 2026-11-21).

Same OpenAI-compatible chat completions as classifier_llm.py, but with
"stream": true: the vendor sends the answer back token by token as
Server-Sent Events (SSE), and we forward each token to the caller as
soon as it arrives instead of waiting for the whole reply.

Why this matters (the FDE interview point):
- One-shot /v1/classify waits for the full answer: time-to-first-token
  == total time. Streaming shows the first token in a fraction of that,
  so a chat UI feels instant even though the total time is similar.
- The cost is the same tokens either way: streaming changes *when* the
  caller sees the text, not *how much* the vendor charges.
- The failure mode is different and worth knowing: with one-shot, an
  error means "no response at all"; with streaming, an error can arrive
  *mid-stream*, after the caller already saw half an answer. That's why
  the generator below yields an {"error": ...} event instead of raising.

Wire format (what curl -N shows):
    data: {"delta": "这句"}
    data: {"delta": "话是反讽……"}
    data: {"done": true, "model": "gpt-4o-mini"}

No key configured? The endpoint still works: it streams one chunk with
the local heuristic's explanation, so the demo never depends on the
network. A mid-stream vendor failure falls back the same way, with
model "local-heuristic-v0-fallback" so the caller can see it happened.
"""
import json
import logging
from collections.abc import Iterator

import httpx

logger = logging.getLogger("project0")

_EXPLAIN_SYSTEM = (
    "You explain in 1-2 short sentences, in Chinese, why a short user "
    "text has a positive, negative or neutral sentiment. "
    "Reply in Chinese only, no JSON, no preamble."
)


def _sse(data: dict) -> str:
    """One Server-Sent Event line: 'data: {...}\\n\\n'."""
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


def _iter_deltas(resp: httpx.Response) -> Iterator[str]:
    """Pull the text deltas out of a vendor SSE stream.

    Skips comment/keep-alive lines (": ping"), skips malformed chunks,
    stops at 'data: [DONE]'. Yields only non-empty text pieces.
    """
    for line in resp.iter_lines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content")
        if delta:
            yield delta


def stream_explanation(
    text: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 30.0,
    fallback_text: str = "模型暂时不可用，这是本地规则的判断。",
    client: httpx.Client | None = None,
) -> Iterator[str]:
    """Yield SSE lines explaining the sentiment of `text`.

    Pass a client only in tests (httpx.MockTransport); in production
    the function builds and closes its own client. With no api_key it
    never touches the network: it streams the fallback text in one go.
    """
    if not api_key:
        yield _sse({"delta": fallback_text})
        yield _sse({"done": True, "model": "local-heuristic-v0"})
        return

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": True,
        "messages": [
            {"role": "system", "content": _EXPLAIN_SYSTEM},
            {"role": "user", "content": text},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=timeout)
    try:
        try:
            with client.stream("POST", url, json=payload, headers=headers) as resp:
                resp.raise_for_status()
                for delta in _iter_deltas(resp):
                    yield _sse({"delta": delta})
        except Exception:
            logger.warning("llm stream failed, falling back", exc_info=True)
            yield _sse({"delta": fallback_text})
            yield _sse({"done": True, "model": "local-heuristic-v0-fallback"})
            return
        yield _sse({"done": True, "model": model})
    finally:
        if own_client:
            client.close()
