from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_messages_pagination():
    response = client.get("/messages?limit=2&offset=0")
    data = response.json()
    assert len(data["data"]) == 2
    assert data["limit"] == 2
    assert data["total"] >= 2

def test_messages_filter_by_from():
    sender = "+919876543210"
    response = client.get(f"/messages?from={sender}")
    for msg in response.json()["data"]:
        assert msg["from"] == sender