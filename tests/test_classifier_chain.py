"""Tests for the auto-switch chain. No network: one MockTransport
routes by host -- the primary vendor's host fails, the secondary's
answers -- so the failover path is exercised for real."""
from types import SimpleNamespace

import httpx

from app.classifier_chain import classify_auto, configured_providers

_PRIMARY = {
    "name": "primary",
    "api_key": "key-1",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
}
_SECONDARY = {
    "name": "secondary",
    "api_key": "key-2",
    "base_url": "https://ws-test.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    "model": "qwen-plus",
}


def _routing_client(primary_status: int = 200, secondary_status: int = 200):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        host = request.url.host
        calls.append(host)
        if "deepseek" in host:
            status = primary_status
        else:
            status = secondary_status
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "boom"}})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"label": "negative", "confidence": 0.93}'}}
                ],
                "usage": {"total_tokens": 40},
            },
        )

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_primary_answers_secondary_not_called():
    client, calls = _routing_client()
    label, conf, model, _ = classify_auto(
        "太差了", providers=[_PRIMARY, _SECONDARY], client=client
    )
    assert (label, conf, model) == ("negative", 0.93, "deepseek-chat")
    assert len(calls) == 1


def test_primary_down_auto_switches_to_secondary():
    client, calls = _routing_client(primary_status=500)
    label, conf, model, _ = classify_auto(
        "太差了", providers=[_PRIMARY, _SECONDARY], client=client
    )
    assert (label, conf, model) == ("negative", 0.93, "qwen-plus")
    assert len(calls) == 2


def test_all_providers_down_raises():
    client, _ = _routing_client(primary_status=500, secondary_status=401)
    try:
        classify_auto("hello", providers=[_PRIMARY, _SECONDARY], client=client)
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError when every provider fails")


def test_no_providers_raises():
    try:
        classify_auto("hello", providers=[])
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError for an empty provider list")


def test_configured_providers_skips_empty_keys():
    cfg = SimpleNamespace(
        llm_api_key="k1",
        llm_base_url="https://api.deepseek.com/v1",
        llm_model="deepseek-chat",
        llm2_api_key="",
        llm2_base_url="",
        llm2_model="",
    )
    providers = configured_providers(cfg)
    assert [p["name"] for p in providers] == ["primary"]

    cfg.llm2_api_key = "k2"
    cfg.llm2_base_url = "https://ws-x.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    cfg.llm2_model = "qwen-plus"
    providers = configured_providers(cfg)
    assert [p["name"] for p in providers] == ["primary", "secondary"]
    assert providers[1]["model"] == "qwen-plus"
