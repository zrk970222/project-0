"""Project 0 — FDE Week 1 starter skeleton.

FastAPI + Pydantic + API-key auth + structured JSON logging.
Deliberately small: Monday's job is the skeleton. Tuesday adds
Dockerfile + GitHub Actions CI, Wednesday/Thursday swap the local
heuristic classifier for real vendor APIs behind the same interface,
Thursday adds a streaming endpoint.
"""
import json
import logging
import time
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from .classifier_chain import classify_auto
from .streaming import stream_explanation


from .config import settings
from .schemas import ClassifyRequest, ClassifyResponse, HealthResponse

logger = logging.getLogger("project0")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="invalid or missing API key")
    return api_key


def configure_logging() -> None:
    """One JSON object per log line: easy to grep, easy to ship to Langfuse later."""

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
            if record.exc_info:
                payload["exc"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


configure_logging()

app = FastAPI(title="project-0", version="0.1.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())[:8]
    start = time.monotonic()
    response = await call_next(request)
    logger.info(
        "request %s %s -> %s in %.1fms request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        (time.monotonic() - start) * 1000,
        request_id,
    )
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="project-0")


_POSITIVE = {"好", "喜欢", "满意", "great", "good", "love", "excellent", "推荐"}
_NEGATIVE = {"差", "糟糕", "失望", "bad", "terrible", "hate", "awful", "退货"}


def _heuristic_label(text: str) -> tuple[str, float]:
    """Local stand-in only. Wed/Thu: replace with vendor API calls,
    keep the request/response models unchanged so callers don't move."""
    lowered = text.lower()
    if any(w in text or w in lowered for w in _POSITIVE):
        return "positive", 0.6
    if any(w in text or w in lowered for w in _NEGATIVE):
        return "negative", 0.6
    return "neutral", 0.5


@app.post("/v1/classify", response_model=ClassifyResponse)
def classify(body: ClassifyRequest, _: str = Depends(verify_api_key)) -> ClassifyResponse:
    if settings.llm_api_key or settings.llm2_api_key:
        try:
            label, confidence, model, _usage = classify_auto(body.text)
        except Exception:
            logger.warning("all llm providers failed, falling back to heuristic", exc_info=True)
            label, confidence = _heuristic_label(body.text)
            model = "local-heuristic-v0-fallback"
    else:
        label, confidence = _heuristic_label(body.text)
        model = "local-heuristic-v0"
    logger.info("classify label=%s confidence=%.2f chars=%d", label, confidence, len(body.text))
    return ClassifyResponse(
        label=label,
        confidence=confidence,
        model=model,
        text_preview=body.text[:80],
    )



def _heuristic_explanation(text: str) -> str:
    """One-line local explanation, for the no-key / fallback path."""
    label, confidence = _heuristic_label(text)
    return f"本地规则判断为 {label}（置信度 {confidence:.2f}）：只数了关键词，没读整句意思。"


@app.get("/v1/stream")
def stream_explain(
    text: str = Query(min_length=1, max_length=5000),
    _: str = Depends(verify_api_key),
):
    """Stream a 1-2 sentence explanation of the text's sentiment, SSE.

    Same vendor + key as /v1/classify (only .env changes vendors).
    No key / vendor failure -> streams the local explanation instead.
    """
    fallback = _heuristic_explanation(text)
    gen = stream_explanation(
        text,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        timeout=settings.llm_timeout,
        fallback_text=fallback,
    )
    return StreamingResponse(gen, media_type="text/event-stream")
