import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client():
    # A fresh application gives every test an independent in-memory job store.
    with TestClient(create_app(settings=Settings())) as test_client:
        yield test_client

