"""
Source Loader - Cinema & Theatre Review Editorial OS v1.0
Discovers, validates, and merges source registry JSON fragments.
"""

import json
from pathlib import Path

from schemas.source_registry import SourceProfile, SourceRegistry


class SourceRegistryMap(dict):
    """
    Dictionary mapping canonical source_id -> SourceProfile that also resolves aliases.
    Iterating and len() strictly reflect canonical sources.
    Lookups ([], get, in) resolve both canonical source_ids and registered aliases.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._aliases: dict[str, str] = {}

    def register_alias(self, alias: str, canonical_id: str) -> None:
        self._aliases[alias] = canonical_id

    def resolve_id(self, source_id_or_alias: str) -> str:
        return self._aliases.get(source_id_or_alias, source_id_or_alias)

    def __getitem__(self, key: str) -> SourceProfile:
        canonical_key = self._aliases.get(key, key)
        return super().__getitem__(canonical_key)

    def get(self, key: str, default=None):
        canonical_key = self._aliases.get(key, key)
        return super().get(canonical_key, default)

    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or (isinstance(key, str) and key in self._aliases)


class SourceLoader:
    def __init__(self, sources_dir: Path | str = "config/sources"):
        self.sources_dir = Path(sources_dir)

    def load_all_sources(self) -> SourceRegistryMap:
        """
        Loads all source registry JSON fragments, validates each with Pydantic,
        detects duplicate source IDs, registers aliases, and returns a SourceRegistryMap.
        """
        if not self.sources_dir.exists():
            raise FileNotFoundError(f"Sources directory not found: {self.sources_dir}")

        sources_by_id = SourceRegistryMap()
        errors: list[str] = []

        # This legacy catalogue is consumed directly by pipeline/acquisition_engine.py.
        # Its top-level "categories" schema predates SourceRegistry and is not a
        # canonical SourceRegistry fragment. Keep the file in place for that
        # legacy consumer, but do not feed it to SourceRegistry.model_validate().
        json_files = sorted(
            path for path in self.sources_dir.glob("*.json")
            if path.name != "editorial_source_registry.json"
        )
        if not json_files:
            raise ValueError(f"No JSON source files found in {self.sources_dir}")

        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Validate with SourceRegistry schema
                registry = SourceRegistry.model_validate(data)
                for profile in registry.sources:
                    if profile.source_id in sources_by_id:
                        errors.append(
                            f"Duplicate source_id '{profile.source_id}' found in {json_file.name} "
                            f"(already defined previously)"
                        )
                    else:
                        sources_by_id[profile.source_id] = profile
                        for alias in profile.aliases:
                            sources_by_id.register_alias(alias, profile.source_id)
            except Exception as e:
                errors.append(f"Failed to load sources from {json_file.name}: {e}")

        if errors:
            raise ValueError("\n".join(errors))

        return sources_by_id
