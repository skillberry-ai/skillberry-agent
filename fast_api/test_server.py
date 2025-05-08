import pytest
from fastapi.testclient import TestClient
from fast_api.api_server import api_server, ChatRequest, ChatMessage


@pytest.fixture
def client():
    """Fixture to create a test client for the FastAPI app."""
    return TestClient(api_server)


def test_api_chat_completion_endpoint(client):
    """Test the /chat/completions endpoint."""
    chat_request = ChatRequest(
        model="test_model",
        messages=[ChatMessage(role="user", content="Hello")],
        temperature=0.7,
        max_tokens=256
    )
    response = client.post("/chat/completions", json=chat_request.dict())
    assert response.status_code == 200
    response_json = response.json()
    assert "choices" in response_json
    assert response_json["choices"][0]["message"]["role"] == "assistant"
    assert "content" in response_json["choices"][0]["message"]


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
