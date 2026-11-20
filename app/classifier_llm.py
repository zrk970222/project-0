"""First real model backend for /v1/classify.

OpenAI-compatible chat completions: the same code talks to OpenAI,
DeepSeek, Qwen/Bailian, GLM ... -- only .env changes (base URL, model,
key). The endpoint contract never changes: label / confidence / model /
text_preview, and the request/response models in schemas.py are untouched.

Design notes (the FDE-relevant bits):
- temperature=0: classification must be deterministic, not creative.
- max_tokens=64: the answer is one short JSON object; don't pay for prose.
- The prompt demands JSON only, and _parse_label tolerates ```json fences.
- Any failure (401, timeout, bad JSON) raises here; main.py catches it
  and falls back to the local heuristic so the endpoint never 500s.
  The fallback is visible in the response: model ends in "-fallback".
"""
import json
import logging
import re

import httpx

logger = logging.getLogger("project0")

LABELS = ("positive", "negative", "neutral")

_SYSTEM = (
    "You classify the sentiment of a short user text. "
    "Reply with JSON only, no other text: "
    '{"label": "positive|negative|neutral", "confidence": 0.0-1.0}. '
    "confidence is how sure you are."
)


def _parse_label(content: str) -> tuple[str, float]:
    """Pull {"label": ..., "confidence": ...} out of the model reply."""
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    label = str(data["label"]).lower().strip()
    if label not in LABELS:
        raise ValueError(f"unknown label: {label!r}")
    confidence = float(data["confidence"])
    return label, min(max(confidence, 0.0), 1.0)


def classify_with_llm(
    text: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
    timeout: float = 15.0,
    client: httpx.Client | None = None,
) -> tuple[str, float, str, dict | None]:
    """Call the vendor and return (label, confidence, model, usage).

    Raises on any failure -- HTTP error, timeout, malformed reply.
    Pass a client only in tests (httpx.MockTransport); in production
    the function builds and closes its own client.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 64,
        "messages": [
            {"role": "system", "content": _SYSTEM},
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
        resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        label, confidence = _parse_label(content)
        usage = data.get("usage")
        if usage:
            logger.info(
                "llm classify model=%s label=%s usage=%s", model, label, usage
            )
        return label, confidence, model, usage
    finally:
        if own_client:
            client.close()
