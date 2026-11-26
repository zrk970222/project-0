"""Tests for the streaming explanation. No real key, no network: the
vendor SSE stream is faked with httpx.MockTransport, so `pytest -q`
stays green offline. Run these *before* wiring the endpoint (like
Friday's tests, they only cover the new module)."""
import httpx

from app.streaming import _sse, stream_explanation


def _sse_body(*chunks: str) -> bytes:
    """Fake a vendor SSE body: one 'data: {...}' line per chunk."""
    out = []
    for c in chunks:
        out.append(f"data: {c}\n\n")
    out.append("data: [DONE]\n\n")
    return "".join(out).encode()


def _chunk(content: str) -> str:
    import json

    return json.dumps({"choices": [{"delta": {"content": content}}]})


def _fake_stream_client(body: bytes, status: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["Authorization"].startswith("Bearer ")
        return httpx.Response(status, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _collect(lines):
    """Join all {"delta": ...} pieces from yielded SSE lines."""
    import json

    text, done = "", None
    for line in lines:
        assert line.startswith("data: ")
        data = json.loads(line[5:])
        text += data.get("delta", "")
        if data.get("done"):
            done = data
    return text, done


def test_streams_deltas_in_order_and_ends_with_done():
    client = _fake_stream_client(
        _sse_body(_chunk("这句"), _chunk("话是反讽"), _chunk("。"))
    )
    text, done = _collect(
        stream_explanation(
            "这服务真是太好了，等了三天都没人理",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            client=client,
        )
    )
    assert text == "这句话是反讽。"
    assert done == {"done": True, "model": "gpt-4o-mini"}


def test_skips_comment_lines_empty_deltas_and_bad_json():
    body = (
        b": ping\n\n"
        + _sse_body(_chunk("好"), "not json at all", _chunk(""))
        .replace(b"data: [DONE]\n\n", b"", 1)
        + b"data: [DONE]\n\n"
    )
    client = _fake_stream_client(body)
    text, done = _collect(
        stream_explanation(
            "很好",
            api_key="test-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            client=client,
        )
    )
    assert text == "好"
    assert done["model"] == "gpt-4o-mini"


def test_vendor_error_falls_back_mid_stream_instead_of_raising():
    client = _fake_stream_client(b"unauthorized", status=401)
    lines = list(
        stream_explanation(
            "很好",
            api_key="bad-key",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            fallback_text="本地规则：看到“好”，判 positive。",
            client=client,
        )
    )
    text, done = _collect(lines)
    assert text == "本地规则：看到“好”，判 positive。"
    assert done == {"done": True, "model": "local-heuristic-v0-fallback"}


def test_no_key_never_touches_the_network():
    # No client at all: with no key the generator must not build one.
    lines = list(
        stream_explanation(
            "很好",
            api_key="",
            base_url="https://api.openai.com/v1",
            model="gpt-4o-mini",
            fallback_text="本地规则：看到“好”，判 positive。",
        )
    )
    text, done = _collect(lines)
    assert text == "本地规则：看到“好”，判 positive。"
    assert done == {"done": True, "model": "local-heuristic-v0"}


def test_sse_helper_format():
    assert _sse({"delta": "你好"}) == 'data: {"delta": "你好"}\n\n'
