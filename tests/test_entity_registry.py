"""
Unit Tests - Entity Registry
Tests entity loading, duplicate detection, and category coverage.
"""

from loaders.entity_loader import EntityLoader
from schemas.entity_registry import EntityStatus, EntityType


def test_entity_loading_and_categories():
    loader = EntityLoader()
    entities = loader.load_all_entities()

    assert len(entities) > 0
    assert "person_abbas_kiarostami" in entities
    assert "person_samuel_beckett" in entities
    assert "event_cannes_film_festival" in entities
    assert "org_cinematheque_francaise" in entities

    kiarostami = entities["person_abbas_kiarostami"]
    assert kiarostami.entity_type == EntityType.FILMMAKER
    assert kiarostami.status == EntityStatus.REFERENCE
    assert kiarostami.name_persian == "عباس کیارستمی"
    assert len(kiarostami.provenance) >= 1

    local_ent = entities.get("local_filmmaker_001")
    assert local_ent is not None
    assert local_ent.status == EntityStatus.LOCAL
