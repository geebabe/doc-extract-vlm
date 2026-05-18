from fastapi.testclient import TestClient
from src.main import app
from src.services.vlm_processor import VLLMDocumentProcessor
from unittest.mock import patch
import pytest

client = TestClient(app)

@pytest.fixture
def mock_processor():
    with patch.object(VLLMDocumentProcessor, 'process') as mock_process:
        yield mock_process

def test_extract_url(mock_processor):
    mock_response = {
        "invoice_number": {"value": "INV-123", "bounding_box": [100, 100, 200, 150]},
        "total_amount": {"value": "1000.0", "bounding_box": [500, 500, 600, 550]}
    }
    mock_processor.return_value = mock_response
    
    response = client.post("/extract/url", json={"url": "https://example.com/image.png"})
    assert response.status_code == 200
    assert response.json() == mock_response

def test_extract_url_failure(mock_processor):
    mock_processor.return_value = None
    response = client.post("/extract/url", json={"url": "https://example.com/image.png"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Extraction failed"}

def test_extract_file(mock_processor):
    mock_response = {
        "invoice_number": {"value": "INV-123", "bounding_box": [100, 100, 200, 150]}
    }
    mock_processor.return_value = mock_response
    
    file_content = b"dummy file content"
    files = {"file": ("test.png", file_content, "image/png")}
    
    response = client.post("/extract/file", files=files)
    assert response.status_code == 200
    assert response.json() == mock_response

def test_health_check():
    response = client.get("/health/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
