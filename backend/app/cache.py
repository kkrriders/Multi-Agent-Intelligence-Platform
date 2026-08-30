"""Response cache key. Whole-run output is cached in the response_cache
table keyed by an exact hash of the inputs that determine the answer:
project, resolved prompt, retrieved chunk set, and how many prior turns
were replayed. Any change misses — that is the only invalidation."""

import hashlib

_SEP = "\x1f"


def cache_key(project_id: str, resolved_input: str, chunk_ids: list[str], history_len: int) -> str:
    material = _SEP.join(
        [
            project_id,
            resolved_input,
            ",".join(sorted(chunk_ids)),
            str(history_len),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
