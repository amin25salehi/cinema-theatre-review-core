"""
Tests for Canonical Hashing Utility
Verifies determinism across key ordering and sensitivity to payload mutations.
"""

from utils.canonical_hash import canonical_json_dumps, compute_canonical_hash


def test_canonical_hash_key_order_invariance():
    payload_a = {
        "title": "Taste of Cherry",
        "director": "Abbas Kiarostami",
        "year": 1997,
        "awards": ["Palme d'Or"],
        "metadata": {"verified": True, "tier": 1},
    }

    # Same semantic payload with reversed key insertion order
    payload_b = {
        "metadata": {"tier": 1, "verified": True},
        "awards": ["Palme d'Or"],
        "year": 1997,
        "director": "Abbas Kiarostami",
        "title": "Taste of Cherry",
    }

    hash_a = compute_canonical_hash(payload_a)
    hash_b = compute_canonical_hash(payload_b)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_canonical_hash_excludes_designated_fields():
    payload = {
        "card_id": "ec_001",
        "headline": "Historic Premiere",
        "card_hash": "existing_stale_hash_value",
        "status": "confirmed",
    }

    hash_without_card_hash = compute_canonical_hash(payload, exclude_fields={"card_hash"})

    payload_altered_card_hash = {
        "card_id": "ec_001",
        "headline": "Historic Premiere",
        "card_hash": "different_arbitrary_value",
        "status": "confirmed",
    }

    hash_after = compute_canonical_hash(payload_altered_card_hash, exclude_fields={"card_hash"})
    assert hash_without_card_hash == hash_after


def test_canonical_hash_sensitivity_to_data_change():
    base_payload = {
        "card_id": "ec_001",
        "headline": "Historic Premiere",
        "claims_count": 5,
    }

    base_hash = compute_canonical_hash(base_payload)

    mutated_payload = {
        "card_id": "ec_001",
        "headline": "Historic Premiere!",  # Single character difference
        "claims_count": 5,
    }

    mutated_hash = compute_canonical_hash(mutated_payload)
    assert base_hash != mutated_hash


def test_canonical_json_dumps_formatting():
    payload = {"b": 2, "a": 1}
    serialized = canonical_json_dumps(payload)
    # Check no extra whitespace around colons and commas
    assert serialized == '{"a":1,"b":2}'
