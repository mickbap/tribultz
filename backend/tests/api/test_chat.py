import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from uuid import uuid4

from app.main import app
from app.api.deps import get_current_user
from app.models.auth import User
from app.services.chat_service import ChatResult, JobEvidence

client = TestClient(app)

# Mock User and Dependency
mock_user = User(
    id=uuid4(),
    email="test@tribultz.com",
    tenant_id=uuid4(),
    full_name="Test User",
    is_active=True
)

def override_get_current_user():
    return mock_user

@pytest.fixture
def mock_chat_service():
    with patch("app.routers.chat.ChatService") as MockService:
        instance = MockService.return_value
        instance.handle_message = AsyncMock()
        yield instance

app.dependency_overrides[get_current_user] = override_get_current_user

def test_chat_happy_path_validate(mock_chat_service):
    # Setup Mock
    expected_cid = uuid4()
    expected_job_id = uuid4()
    
    # Mock handle_message return
    mock_chat_service.handle_message.return_value = ChatResult(
        conversation_id=expected_cid,
        response_markdown="Job started",
        evidence=[
            JobEvidence(type="job", job_id=expected_job_id, href=f"/jobs/{expected_job_id}", label="Validation Job")
        ]
    )

    response = client.post("/api/v1/chat/message", json={"message": "Validate invoice INV-999"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == str(expected_cid)
    assert data["response_markdown"] == "Job started"
    assert len(data["evidence"]) == 1
    assert data["evidence"][0]["job_id"] == str(expected_job_id)
    assert data["evidence"][0]["type"] == "job"

    # Verify usage of strict scoping
    mock_chat_service.handle_message.assert_called_once()
    call_kwargs = mock_chat_service.handle_message.call_args.kwargs
    assert call_kwargs["tenant_id"] == mock_user.tenant_id
    assert call_kwargs["user_id"] == mock_user.id
    assert call_kwargs["message"] == "Validate invoice INV-999"
    assert call_kwargs["conversation_id"] is None

def test_chat_with_valid_conversation_id(mock_chat_service):
    cid = uuid4()
    mock_chat_service.handle_message.return_value = ChatResult(
        conversation_id=cid,
        response_markdown="Continued",
        evidence=[]
    )
    
    response = client.post("/api/v1/chat/message", json={
        "message": "Continue",
        "conversation_id": str(cid)
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == str(cid)
    
    call_kwargs = mock_chat_service.handle_message.call_args.kwargs
    assert call_kwargs["conversation_id"] == cid

def test_chat_payload_validation_max_length():
    long_msg = "a" * 4001
    response = client.post("/api/v1/chat/message", json={"message": long_msg})
    assert response.status_code == 422

def test_chat_payload_validation_empty():
    response = client.post("/api/v1/chat/message", json={"message": ""})
    assert response.status_code == 422
