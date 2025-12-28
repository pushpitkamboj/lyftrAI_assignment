import os
import hmac
import hashlib
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_webhook_invalid_signature():
    payload = {"message_id": "m1", "from": "+919876543210", "to": "+14155550100", "ts": "2025-01-15T10:00:00Z", "text": "Hello"}
    response = client.post("/webhook", json=payload, headers={"X-Signature": "wrong-sig"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid_signature"

def test_webhook_success_and_idempotency():
    payload = {"message_id": "m2", "from": "+919876543210", "to": "+14155550100", "ts": "2025-01-15T10:00:00Z", "text": "Hello"}
    body_bytes = b'{"message_id": "m2", "from": "+919876543210", "to": "+14155550100", "ts": "2025-01-15T10:00:00Z", "text": "Hello"}'
    
    # Generate valid signature
    sig = hmac.new(os.getenv("WEBHOOK_SECRET").encode(), body_bytes, hashlib.sha256).hexdigest()
    
    # First call: Created
    resp1 = client.post("/webhook", content=body_bytes, headers={"X-Signature": sig, "Content-Type": "application/json"})
    assert resp1.status_code == 200
    assert resp1.json() == {"status": "ok"}

    # Second call: Duplicate (Idempotent)
    resp2 = client.post("/webhook", content=body_bytes, headers={"X-Signature": sig, "Content-Type": "application/json"})
    assert resp2.status_code == 200
    assert resp2.json() == {"status": "ok"}