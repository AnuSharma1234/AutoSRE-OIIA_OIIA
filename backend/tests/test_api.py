"""
End-to-end API integration tests for the AutoSRE backend.

Tests use mocked DB sessions and mocked external services (kubectl, Claude).
Run with: cd backend && pytest tests/ -v
"""
import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Result

from app.core.database import get_db
from app.main import app
from app.models.incident import Incident
from app.schemas.incident import AlertType, IncidentStatus
from app.services.remediation import CommandResult


@pytest.fixture
def client():
    return TestClient(app)


def make_mock_result(incident_or_list):
    """Create a mock Result object from sqlalchemy."""
    mock = MagicMock(spec=Result)
    mock.scalar_one_or_none.return_value = incident_or_list
    mock.scalars.return_value.all.return_value = incident_or_list if isinstance(incident_or_list, list) else []
    mock.scalar.return_value = 0
    return mock


def make_mock_result_list(items):
    """Create a mock Result for a list of items."""
    mock = MagicMock(spec=Result)
    mock.scalar_one_or_none.return_value = items[0] if items else None
    mock.scalars.return_value.all.return_value = items
    mock.scalar.return_value = len(items)
    return mock


def mock_session(results: dict[str, MagicMock]):
    """Build a mock AsyncSession that returns configured results per query."""
    session = AsyncMock()
    async def fake_execute(query):
        stmt_str = str(query.compile(compile_kwargs={"literal_binds": True}))
        for key, result in results.items():
            if key in stmt_str:
                return result
        return MagicMock(spec=Result)
    session.execute = fake_execute
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    return session


def override_get_db(mock_session):
    async def _override():
        yield mock_session
    return _override


class TestIncidentsEndpoints:
    """Tests for /api/v1/incidents endpoints."""

    def test_list_incidents(self, client: TestClient):
        """GET /incidents returns 200 and correct list schema."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = uuid.uuid4()
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "PENDING"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()
        mock_incident.resolved_at = None

        mock_result = make_mock_result_list([mock_incident])
        session = mock_session({
            "SELECT": mock_result,
            "FROM": mock_result,
        })
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.get("/api/v1/incidents/")
            assert response.status_code == 200
            data = response.json()
            assert "incidents" in data
            assert "total" in data
            assert "page" in data
            assert "limit" in data
            assert isinstance(data["incidents"], list)
        finally:
            app.dependency_overrides.clear()

    def test_get_incident_404(self, client: TestClient):
        """GET /incidents/{invalid_uuid} returns 404."""
        empty_result = make_mock_result(None)
        session = mock_session({"incidents": empty_result})
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.get(
                f"/api/v1/incidents/{uuid.uuid4()}"
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()

    def test_get_incident_detail(self, client: TestClient, sample_incident_id: uuid.UUID):
        """GET /incidents/{id} returns 200 with incident + analysis + action_logs."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "PENDING"
        mock_incident.extra_data = {"namespace": "default"}
        mock_incident.created_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_incident.resolved_at = None

        incident_result = make_mock_result(mock_incident)
        empty_result = make_mock_result_list([])
        session = mock_session({
            "incident": incident_result,
            "incidents": incident_result,
        })
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.get(f"/api/v1/incidents/{sample_incident_id}")
            assert response.status_code == 200
            data = response.json()
            assert "incident" in data
            assert "analysis" in data
            assert "action_logs" in data
            assert data["incident"]["cluster_id"] == "test-cluster"
        finally:
            app.dependency_overrides.clear()

    def test_audit_endpoint_schema(self, client: TestClient, sample_incident_id: uuid.UUID):
        """GET /incidents/{id}/audit returns 200 with list of audit entries."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "PENDING"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime(2024, 1, 1, 12, 0, 0)
        mock_incident.resolved_at = None

        mock_action_log = MagicMock()
        mock_action_log.id = uuid.uuid4()
        mock_action_log.incident_id = sample_incident_id
        mock_action_log.command = "kubectl delete pod test-pod -n default"
        mock_action_log.status = "SUCCESS"
        mock_action_log.result = "pod deleted"
        mock_action_log.timestamp = datetime(2024, 1, 1, 12, 5, 0)
        mock_action_log.confidence_score = 0.95

        incident_result = make_mock_result(mock_incident)
        logs_result = make_mock_result_list([mock_action_log])
        session = mock_session({
            "incident": incident_result,
            "incidents": incident_result,
        })
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.get(f"/api/v1/incidents/{sample_incident_id}/audit")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
        finally:
            app.dependency_overrides.clear()


class TestClusterEndpoint:
    """Tests for /api/v1/cluster endpoints."""

    def test_cluster_overview_endpoint(self, client: TestClient):
        """GET /cluster/overview returns 200 with nodes/namespaces/pod_summary."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = uuid.uuid4()
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "PENDING"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()

        incidents_result = make_mock_result_list([mock_incident])
        session = mock_session({
            "incident": incidents_result,
            "incidents": incidents_result,
        })

        with patch("app.api.v1.cluster.get_cluster_info") as mock_k8s:
            mock_k8s.return_value = {
                "nodes": [{"name": "node-1", "status": "Ready", "roles": []}],
                "namespaces": ["default", "kube-system"],
                "pod_summary": {"total": 10, "running": 8, "pending": 1, "failed": 1},
            }
            app.dependency_overrides[get_db] = override_get_db(session)

            try:
                response = client.get("/api/v1/cluster/overview")
                assert response.status_code == 200
                data = response.json()
                assert "nodes" in data
                assert "namespaces" in data
                assert "pod_summary" in data
                assert "recent_incidents" in data
                assert isinstance(data["pod_summary"], dict)
                assert "total" in data["pod_summary"]
            finally:
                app.dependency_overrides.clear()


class TestExecuteEndpoint:
    """Tests for /api/v1/execute endpoints."""

    def test_execute_approval_required(
        self, client: TestClient, sample_incident_id: uuid.UUID
    ):
        """POST /execute with approved=true when incident is APPROVAL_REQUIRED."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "APPROVAL_REQUIRED"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()
        mock_incident.resolved_at = None
        mock_incident.attempt_count = "1"

        incident_result = make_mock_result(mock_incident)
        empty_result = make_mock_result_list([])
        session = mock_session({
            "incident": incident_result,
            "incidents": incident_result,
        })

        with patch("app.api.v1.execute.execute_command") as mock_cmd:
            mock_cmd.return_value = CommandResult(
                success=True,
                output="pod deleted",
                error="",
                command="kubectl delete pod test-pod -n default",
            )
            app.dependency_overrides[get_db] = override_get_db(session)

            try:
                response = client.post(
                    "/api/v1/execute/",
                    json={
                        "incident_id": str(sample_incident_id),
                        "command": "kubectl delete pod test-pod -n default",
                        "approved": True,
                    },
                )
                assert response.status_code == 200
                data = response.json()
                assert "status" in data
                assert "action_log_id" in data
            finally:
                app.dependency_overrides.clear()

    def test_execute_reject(
        self, client: TestClient, sample_incident_id: uuid.UUID
    ):
        """POST /execute with approved=false escalates incident."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "APPROVAL_REQUIRED"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()
        mock_incident.resolved_at = None
        mock_incident.attempt_count = "1"

        incident_result = make_mock_result(mock_incident)
        session = mock_session({"incident": incident_result})
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.post(
                "/api/v1/execute/",
                json={
                    "incident_id": str(sample_incident_id),
                    "command": "kubectl delete pod test-pod -n default",
                    "approved": False,
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "REJECTED"
        finally:
            app.dependency_overrides.clear()

    def test_execute_wrong_status(
        self, client: TestClient, sample_incident_id: uuid.UUID
    ):
        """POST /execute when incident NOT in APPROVAL_REQUIRED returns 400."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "PENDING"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()
        mock_incident.resolved_at = None
        mock_incident.attempt_count = "0"

        incident_result = make_mock_result(mock_incident)
        session = mock_session({"incident": incident_result})
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.post(
                "/api/v1/execute/",
                json={
                    "incident_id": str(sample_incident_id),
                    "command": "kubectl delete pod test-pod -n default",
                    "approved": True,
                },
            )
            assert response.status_code == 400
            assert "APPROVAL_REQUIRED" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_whitelist_rejects_dangerous(self, client: TestClient, sample_incident_id: uuid.UUID):
        """POST /execute with disallowed command returns 400."""
        mock_incident = MagicMock(spec=Incident)
        mock_incident.id = sample_incident_id
        mock_incident.alert_type = "CRASHLOOP"
        mock_incident.cluster_id = "test-cluster"
        mock_incident.status = "APPROVAL_REQUIRED"
        mock_incident.extra_data = {}
        mock_incident.created_at = datetime.utcnow()
        mock_incident.resolved_at = None
        mock_incident.attempt_count = "1"

        incident_result = make_mock_result(mock_incident)
        session = mock_session({"incident": incident_result})
        app.dependency_overrides[get_db] = override_get_db(session)

        try:
            response = client.post(
                "/api/v1/execute/",
                json={
                    "incident_id": str(sample_incident_id),
                    "command": "kubectl delete namespace default",
                    "approved": True,
                },
            )
            assert response.status_code == 400
            assert "not allowed" in response.json()["detail"].lower()
        finally:
            app.dependency_overrides.clear()
