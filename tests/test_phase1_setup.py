from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "screamerscreener"
    assert "version" in payload


def test_project_layout_exists() -> None:
    expected = [
        "backend/main.py",
        "backend/config.py",
        "backend/data/provider.py",
        "backend/data/eodhd.py",
        "backend/data/freecryptoapi.py",
        "backend/ingestion/initial_load.py",
        "backend/ingestion/sync_market_data.py",
        "backend/ingestion/initial_load_crypto.py",
        "backend/ingestion/sync_crypto_data.py",
        "frontend/package.json",
        "supabase/migrations",
        ".env.example",
        "requirements.txt",
        "README.md",
    ]
    missing = [path for path in expected if not (ROOT / path).exists()]
    assert missing == [], f"Missing Phase 1 paths: {missing}"
