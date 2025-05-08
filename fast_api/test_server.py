import pytest
from fastapi.testclient import TestClient
from fast_api.api_server import api_server, ChatRequest, ChatMessage


@pytest.fixture
def client():
    """Fixture to create a test client for the FastAPI app."""
    return TestClient(api_server)


def test_api_prompt_endpoint(client):
    """Test the /prompt endpoint."""
    response = client.post("/prompt", params={"user_prompt": "test prompt"})
    assert response.status_code == 500


def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
