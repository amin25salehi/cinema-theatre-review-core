"""
Config Loader - Cinema & Theatre Review Editorial OS v1.0.1
Loads and parses core configuration files into strict Pydantic v2 schemas.
"""

import json
from pathlib import Path
from typing import Any

from schemas.authority_map import AuthorityMap
from schemas.editorial_rules import EditorialRules
from schemas.iran_exceptions import IranExceptionsPolicy
from schemas.taxonomy import ContentTaxonomy


class ConfigLoader:
    def __init__(self, config_dir: Path | str = "config"):
        self.config_dir = Path(config_dir)

    def load_json(self, relative_path: str) -> dict[str, Any]:
        file_path = self.config_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_authority_map(self) -> AuthorityMap:
        data = self.load_json("authority_map.json")
        return AuthorityMap.model_validate(data)

    def load_editorial_rules(self) -> EditorialRules:
        data = self.load_json("editorial_rules.json")
        return EditorialRules.model_validate(data)

    def load_content_taxonomy(self) -> ContentTaxonomy:
        data = self.load_json("content_taxonomy.json")
        return ContentTaxonomy.model_validate(data)

    def load_iran_exceptions(self) -> IranExceptionsPolicy:
        data = self.load_json("iran_exceptions.json")
        return IranExceptionsPolicy.model_validate(data)

    def load_source_registry(self) -> dict[str, Any]:
        from loaders.source_loader import SourceLoader
        return SourceLoader(self.config_dir / "sources").load_all_sources()
