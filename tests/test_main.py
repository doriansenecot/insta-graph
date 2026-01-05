"""Tests for FastAPI endpoints."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def mock_redis():
    """Mock Redis client with proper job storage."""
    storage = {}

    def mock_get(key):
        return storage.get(key)

    def mock_set(key, value):
        storage[key] = value
        return True

    mock = MagicMock()
    mock.get.side_effect = mock_get
    mock.set.side_effect = mock_set
    return mock


@pytest.fixture
def mock_scraper():
    """Mock InstagramScraper."""
    mock = MagicMock()
    mock.login.return_value = True
    mock.analyze_recursive.return_value = []
    return mock


@pytest.fixture
def client(mock_redis, mock_scraper):
    """Create test client with mocked dependencies."""
    with (
        patch("app.main.redis_client", mock_redis),
        patch("app.main.scraper", mock_scraper),
        patch("redis.from_url", return_value=mock_redis),
        patch("app.main.InstagramScraper", return_value=mock_scraper),
    ):
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    def test_health_returns_healthy(self, client):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestAnalyzeEndpoint:
    """Tests for /analyze endpoint."""

    def test_analyze_creates_job(self, client, mock_redis):
        """POST /analyze should create a new job."""
        mock_redis.get.return_value = None
        
        response = client.post(
            "/analyze",
            json={"username": "testuser", "depth": 1}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["target_username"] == "testuser"
        assert data["depth"] == 1

    def test_analyze_validates_username(self, client):
        """POST /analyze should validate username length."""
        response = client.post(
            "/analyze",
            json={"username": "", "depth": 1}
        )
        assert response.status_code == 422

    def test_analyze_validates_depth(self, client):
        """POST /analyze should validate depth range."""
        response = client.post(
            "/analyze",
            json={"username": "testuser", "depth": 0}
        )
        assert response.status_code == 422

    def test_analyze_default_depth(self, client):
        """POST /analyze should use default depth of 1."""
        response = client.post(
            "/analyze",
            json={"username": "testuser"}
        )
        assert response.status_code == 200
        assert response.json()["depth"] == 1


class TestGetAnalysisEndpoint:
    """Tests for GET /analyze/{job_id} endpoint."""

    def test_get_analysis_not_found(self, client, mock_redis):
        """GET /analyze/{job_id} should return 404 for unknown job."""
        response = client.get("/analyze/unknown-job-id")
        assert response.status_code == 404

    def test_get_analysis_returns_job(self, client, mock_redis):
        """GET /analyze/{job_id} should return job data."""
        # Pre-populate job in mock storage
        mock_redis.set(
            "job:test-job-id",
            json.dumps({
                "job_id": "test-job-id",
                "status": "completed",
                "target_username": "testuser",
                "depth": 1,
                "min_followers": 3000,
                "results": [],
                "error": None,
                "progress": "Completed",
            }),
        )

        response = client.get("/analyze/test-job-id")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id"
        assert data["status"] == "completed"
