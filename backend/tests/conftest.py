import os
import uuid
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("gemini_api_key", "test-key")
os.environ.setdefault("database_url", "postgresql+asyncpg://localhost/test")
os.environ.setdefault("redis_url", "redis://localhost")
os.environ.setdefault("cluster_id", "test-cluster")
os.environ.setdefault("api_secret_key", "test-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture(scope="session")
def event_loop():
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_incident_id() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def sample_incident(sample_incident_id: uuid.UUID) -> MagicMock:
    incident = MagicMock()
    incident.id = sample_incident_id
    incident.alert_type = "CRASHLOOP"
    incident.cluster_id = "test-cluster"
    incident.status = "PENDING"
    incident.extra_data = {"namespace": "default", "pod_name": "test-pod"}
    incident.created_at = datetime(2024, 1, 1, 12, 0, 0)
    incident.resolved_at = None
    incident.attempt_count = "0"
    return incident


@pytest.fixture
def sample_incident_approval_required(sample_incident_id: uuid.UUID) -> MagicMock:
    incident = MagicMock()
    incident.id = sample_incident_id
    incident.alert_type = "CRASHLOOP"
    incident.cluster_id = "test-cluster"
    incident.status = "APPROVAL_REQUIRED"
    incident.extra_data = {"namespace": "default", "pod_name": "test-pod"}
    incident.created_at = datetime(2024, 1, 1, 12, 0, 0)
    incident.resolved_at = None
    incident.attempt_count = "1"
    return incident


@pytest.fixture
def test_client() -> TestClient:
    from app.main import app
    return TestClient(app)


@pytest.fixture
def mock_kubernetes():
    with patch("app.services.kubernetes._run_kubectl") as mock:
        mock.return_value = ("{}", "", 0)
        yield mock


@pytest.fixture
def mock_remediation():
    with patch("app.services.remediation.execute_command") as mock:
        yield mock
