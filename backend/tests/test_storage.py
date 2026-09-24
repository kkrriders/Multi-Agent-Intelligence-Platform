import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://maip_app:x@localhost:5433/maip")
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ.setdefault("GROQ_API_KEY", "test")

from app import storage
from app.config import settings


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "document_storage_dir", str(tmp_path))
    return tmp_path


def test_save_then_delete(root):
    storage.save("p/d/a.txt", b"hi")
    assert (root / "p/d/a.txt").read_bytes() == b"hi"
    storage.delete("p/d/a.txt")
    assert not (root / "p/d/a.txt").exists()
    storage.delete("p/d/a.txt")  # missing file is fine


@pytest.mark.parametrize("bad", ["../evil.txt", "p/../../evil.txt", "/etc/passwd"])
def test_rejects_path_traversal(bad):
    with pytest.raises(ValueError):
        storage.save(bad, b"x")
