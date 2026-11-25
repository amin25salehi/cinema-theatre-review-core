"""
Canonical Hashing Utility - Cinema & Theatre Review Editorial OS v1.0.1
Provides deterministic serialization and SHA-256 hashing for audit artifacts.
"""

import hashlib
import json
from typing import Any


def canonical_json_dumps(obj: Any) -> str:
    """
    Deterministically serializes any dictionary, list, or primitive to JSON.
    - Keys are sorted alphabetically at all nesting levels.
    - No redundant whitespace (separators are (',', ':')).
    - UTF-8 characters are preserved without ASCII escape sequences.
    """
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_canonical_hash(
    data: dict[str, Any],
    exclude_fields: set[str] | list[str] | None = None,
) -> str:
    """
    Computes a canonical SHA-256 hash of a dictionary.
    Excludes specified field names (e.g. 'card_hash' or 'integrity_checksum').
    """
    exclude = set(exclude_fields or [])

    def _strip_excluded(val: Any) -> Any:
        if isinstance(val, dict):
            return {
                k: _strip_excluded(v)
                for k, v in val.items()
                if k not in exclude
            }
        elif isinstance(val, list):
            return [_strip_excluded(item) for item in val]
        return val

    cleaned = _strip_excluded(data)
    canonical_str = canonical_json_dumps(cleaned)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
