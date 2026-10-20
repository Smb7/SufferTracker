import os

os.environ["AUTO_MIGRATE"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["JWT_KEY"] = "unit-test-signing-key-0123456789abcdef"
os.environ["DATABASE_URL"] = "sqlite://"

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app

get_settings.cache_clear()


def test_health_reports_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
