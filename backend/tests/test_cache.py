from app.cache import cache_key

BASE = dict(project_id="p1", resolved_input="what is x?", chunk_ids=["a", "b"], history_len=2)


def test_cache_key_is_sha256_hex():
    key = cache_key(**BASE)
    assert len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)


def test_cache_key_is_stable_across_chunk_id_order():
    assert cache_key(**{**BASE, "chunk_ids": ["a", "b"]}) == cache_key(**{**BASE, "chunk_ids": ["b", "a"]})


def test_cache_key_changes_with_input():
    assert cache_key(**BASE) != cache_key(**{**BASE, "resolved_input": "what is y?"})


def test_cache_key_changes_with_chunk_set():
    assert cache_key(**BASE) != cache_key(**{**BASE, "chunk_ids": ["a", "b", "c"]})


def test_cache_key_changes_with_history_len():
    assert cache_key(**BASE) != cache_key(**{**BASE, "history_len": 3})


def test_cache_key_changes_with_project():
    assert cache_key(**BASE) != cache_key(**{**BASE, "project_id": "p2"})


def test_cache_key_no_chunks_is_stable():
    assert cache_key(**{**BASE, "chunk_ids": []}) == cache_key(**{**BASE, "chunk_ids": []})
