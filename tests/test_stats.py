from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)

def test_stats_counts():
    response = client.get("/stats")
    data = response.json()
    assert "total_messages" in data 
    assert "messages_per_sender" in data
    
    # Ensure list is sorted by count desc
    counts = [item["count"] for item in data["messages_per_sender"]]
    assert counts == sorted(counts, reverse=True)