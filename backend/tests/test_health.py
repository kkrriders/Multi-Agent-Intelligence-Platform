import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
