"""Tests for the LLM classifier. No real key, no network: the vendor
is faked with httpx.MockTransport, so `pytest -q` stays green offline."""
import httpx

from app.classifier_llm import classify_with_llm


def _fake_client(body: dict, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(status, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _ok_body(content: str) -> dict:
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {"prompt_tokens": 42, "completion_tokens": 12, "total_tokens": 54},
    }


def test_llm_positive_parses_json():
    client = _fake_client(
        _ok_body('{"label": "positive", "confidence": 0.87}')
    )
    label, conf, model, usage = classify_with_llm(
        "这个产品很好，我很满意",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        client=client,
    )
    assert (label, conf, model) == ("positive", 0.87, "gpt-4o-mini")
    assert usage["total_tokens"] == 54


def test_llm_tolerates_markdown_fences():
    client = _fake_client(
        _ok_body('```json\n{"label": "negative", "confidence": 0.9}\n```')
    )
    label, conf, _, _ = classify_with_llm(
        "太差了，很失望",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        client=client,
    )
    assert (label, conf) == ("negative", 0.9)


def test_llm_bad_json_raises_so_caller_can_fall_back():
    client = _fake_client(_ok_body("not json at all"))
    try:
        classify_with_llm(
            "hello",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            client=client,
        )
    except ValueError:
        return
    raise AssertionError("expected ValueError for malformed model reply")


def test_llm_http_error_raises():
    client = _fake_client({"error": {"message": "Incorrect API key"}}, status=401)
    try:
        classify_with_llm(
            "hello",
            api_key="bad-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            client=client,
        )
    except httpx.HTTPStatusError:
        return
    raise AssertionError("expected HTTPStatusError on 401")
