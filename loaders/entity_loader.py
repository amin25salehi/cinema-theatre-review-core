"""
Entity Loader - Cinema & Theatre Review Editorial OS v1.0
Discovers, validates, and merges entity registry JSON fragments.
Supports reference, recognized, emerging, and local entities.
"""

import json
from pathlib import Path

from schemas.entity_registry import EntityProfile, EntityRegistry


class EntityLoader:
    def __init__(self, entities_dir: Path | str = "config/entities"):
        self.entities_dir = Path(entities_dir)

    def load_all_entities(self) -> dict[str, EntityProfile]:
        """
        Loads all entity registry JSON fragments, validates each with Pydantic,
        detects duplicate entity IDs, and returns a dictionary indexed by entity_id.
        """
        if not self.entities_dir.exists():
            raise FileNotFoundError(f"Entities directory not found: {self.entities_dir}")

        entities_by_id: dict[str, EntityProfile] = {}
        errors: list[str] = []

        json_files = sorted(list(self.entities_dir.glob("*.json")))
        if not json_files:
            raise ValueError(f"No JSON entity files found in {self.entities_dir}")

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Validate with EntityRegistry schema
                registry = EntityRegistry.model_validate(data)
                for profile in registry.entities:
                    if profile.entity_id in entities_by_id:
                        errors.append(
                            f"Duplicate entity_id '{profile.entity_id}' found in {json_file.name} "
                            f"(already defined previously)"
                        )
                    else:
                        entities_by_id[profile.entity_id] = profile
            except Exception as e:
                errors.append(f"Failed to load entities from {json_file.name}: {e}")

        if errors:
            raise ValueError("\n".join(errors))

        return entities_by_id
