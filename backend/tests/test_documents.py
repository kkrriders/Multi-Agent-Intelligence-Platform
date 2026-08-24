import os
import pytest

os.environ.setdefault("SUPABASE_URL", "http://localhost")
os.environ.setdefault("SUPABASE_ANON_KEY", "test")
os.environ.setdefault("GROQ_API_KEY", "test")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_document_requires_auth():
    response = client.post(
        "/projects/some-id/documents",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code in (401, 422)


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_upload_rejects_unsupported_mime_type(auth_headers):
    project_response = client.post("/projects", json={"name": "Doc Reject Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("data.bin", b"\x00\x01", "application/octet-stream")},
        headers=auth_headers,
    )
    assert response.status_code == 422


@pytest.mark.skipif(
    os.environ.get("SUPABASE_URL", "http://localhost") == "http://localhost",
    reason="Real Supabase project required for this integration test",
)
def test_upload_list_and_delete_document(auth_headers, qdrant_available):
    project_response = client.post("/projects", json={"name": "Doc Test Project"}, headers=auth_headers)
    project_id = project_response.json()["id"]

    content = ("word " * 200).encode("utf-8")  # long enough to produce multiple 800-char chunks
    upload_response = client.post(
        f"/projects/{project_id}/documents",
        files={"file": ("notes.txt", content, "text/plain")},
        headers=auth_headers,
    )
    assert upload_response.status_code == 200
    document = upload_response.json()
    assert document["status"] == "indexed"
    assert document["filename"] == "notes.txt"

    list_response = client.get(f"/projects/{project_id}/documents", headers=auth_headers)
    assert list_response.status_code == 200
    assert any(d["id"] == document["id"] for d in list_response.json())

    delete_response = client.delete(
        f"/projects/{project_id}/documents/{document['id']}", headers=auth_headers
    )
    assert delete_response.status_code == 200

    list_after_delete = client.get(f"/projects/{project_id}/documents", headers=auth_headers)
    assert not any(d["id"] == document["id"] for d in list_after_delete.json())
