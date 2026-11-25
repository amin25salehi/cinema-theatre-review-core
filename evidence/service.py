"""
Evidence Acquisition Service - Cinema & Theatre Review Editorial OS v1.0.1
Stage 8.7: Evidence Acquisition & Evidence Cards.

Orchestrates:
- Candidate / Story / Claim alignment
- Evidence acquisition and synthesis into EvidenceCard
- Deterministic authority resolution using AuthorityMap
- Explicit conflict detection and handling
- Strict referential integrity verification via EvidenceCardValidator
- State isolation in data/evidence_state.json

Strict Invariants:
- 0 LLM calls, 0 embeddings, 0 semantic inference
- Deterministic authority evaluation (AuthorityEvaluator)
- Material unresolved conflict -> card status CONFLICTED / UNRESOLVED (Evidence layer NEVER decides publication)
- Referential integrity with Source Registry & Entity Registry
- ImmutableStrictModel contracts
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from evidence.authority_evaluator import AuthorityEvaluator
from evidence.card_validator import EvidenceCardValidator
from evidence.claim_builder import ClaimBuilder
from evidence.evidence_builder import EvidenceBuilder
from evidence.evidence_card_builder import EvidenceCardBuilder
from evidence.state import DEFAULT_EVIDENCE_STATE_FILE, EvidenceStateStore
from loaders.config_loader import ConfigLoader
from loaders.entity_loader import EntityLoader
from loaders.source_loader import SourceLoader
from schemas.authority_map import AuthorityMap
from schemas.candidate import Candidate
from schemas.entity_registry import EntityProfile
from schemas.evidence_card import (
    Claim,
    ConflictItem,
    EntityReference,
    EvidenceCard,
    EvidenceItem,
    ImageEvidenceItem,
)
from schemas.source_registry import SourceProfile


class EvidenceAcquisitionService:
    """
    Main orchestration service for Stage 8.7 Evidence Acquisition and Card synthesis.
    """

    def __init__(
        self,
        config_dir: str | Path = "config",
        sources_dir: str | Path = "config/sources",
        entities_dir: str | Path = "config/entities",
        state_file: str | Path = DEFAULT_EVIDENCE_STATE_FILE,
        authority_map: Optional[AuthorityMap] = None,
        sources: Optional[dict[str, SourceProfile]] = None,
        entities: Optional[dict[str, EntityProfile]] = None,
    ):
        # 1. Load registries & config
        if sources is not None:
            self.sources = sources
        else:
            source_loader = SourceLoader(sources_dir)
            self.sources = source_loader.load_all_sources()

        if entities is not None:
            self.entities = entities
        else:
            entity_loader = EntityLoader(entities_dir)
            self.entities = entity_loader.load_all_entities()

        config_loader = ConfigLoader(config_dir)
        if authority_map is not None:
            self.authority_map = authority_map
        else:
            self.authority_map = config_loader.load_authority_map()

        taxonomy = config_loader.load_content_taxonomy()
        self.valid_claim_types = {ct.code for ct in taxonomy.claim_types}

        # 2. Initialize builder and state store
        self.builder = EvidenceCardBuilder(
            authority_map=self.authority_map,
            sources=self.sources,
            entity_registry_version="1.0.0",
            source_registry_version="1.0.0",
            content_taxonomy_version=taxonomy.version,
            editorial_rules_version="1.0.0",
            iran_exceptions_version="1.0.0",
        )
        self.state_store = EvidenceStateStore(state_file=state_file)
        self.state_store.load()

    def synthesize_card(
        self,
        card_id: str,
        story_id: str,
        headline_working: str,
        target_topic: str,
        entities: list[EntityReference],
        claims: list[Claim],
        evidence: list[EvidenceItem],
        version: int = 1,
        created_at: str | None = None,
        summary_draft: str | None = None,
        images: list[ImageEvidenceItem] | None = None,
        validate: bool = True,
        persist_state: bool = True,
    ) -> EvidenceCard:
        """
        Builds a canonical, immutable EvidenceCard, validates referential integrity,
        and records the snapshot in state store.
        """
        card = self.builder.build_card(
            card_id=card_id,
            story_id=story_id,
            headline_working=headline_working,
            target_topic=target_topic,
            entities=entities,
            claims=claims,
            evidence=evidence,
            images=images,
            summary_draft=summary_draft,
            version=version,
            created_at=created_at,
        )

        if validate:
            EvidenceCardValidator.assert_valid(card, self.entities, self.sources)

        if persist_state:
            has_conflicts = len(card.conflicts) > 0
            self.state_store.register_card(
                card_id=card.identity.card_id,
                version=card.identity.version,
                story_id=card.identity.story_id,
                card_hash=card.integrity.card_hash,
                claims_count=len(card.claims),
                evidence_count=len(card.evidence),
                has_conflicts=has_conflicts,
                snapshot_json=card.model_dump_json(),
            )
            self.state_store.save()

        return card

    def get_persisted_card(self, card_id: str) -> Optional[EvidenceCard]:
        """
        Retrieves and reconstructs an EvidenceCard from state store.
        """
        entry = self.state_store.get_card(card_id)
        if entry and entry.snapshot_json:
            return EvidenceCard.model_validate_json(entry.snapshot_json)
        return None
