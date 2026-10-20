import os

os.environ["AUTO_MIGRATE"] = "false"
os.environ["APP_ENV"] = "development"
os.environ["JWT_KEY"] = "unit-test-signing-key-0123456789abcdef"
os.environ["JWT_ISSUER"] = "SufferTracker.Tests"
os.environ["JWT_AUDIENCE"] = "SufferTracker.Tests.Clients"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_EMAILS"] = "smoke@test.com"
os.environ["ADMIN_PASSWORD"] = ""

import pytest
from fastapi.testclient import TestClient

from app import models  # noqa: F401
from app.config import get_settings
from app.database import Base, SessionLocal, engine

get_settings.cache_clear()


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
