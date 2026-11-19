from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
KEY = {"X-API-Key": "dev-only-change-me"}


def test_health_is_public():
    assert client.get("/health").json() == {"status": "ok", "service": "project-0"}


def test_classify_requires_api_key():
    assert client.post("/v1/classify", json={"text": "很好"}).status_code == 401


def test_classify_heuristic_and_validation():
    r = client.post("/v1/classify", json={"text": "这个产品很好，我很满意"}, headers=KEY)
    assert r.status_code == 200
    assert r.json()["label"] == "positive"
    assert r.json()["model"] == "local-heuristic-v0"
    assert client.post("/v1/classify", json={"text": ""}, headers=KEY).status_code == 422
