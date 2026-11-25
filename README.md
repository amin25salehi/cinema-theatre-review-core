# Cinema & Theatre Review — Editorial OS / Data & Editorial Core v1.0.1

An authoritative, Persian-language, AI-assisted editorial operating system for discovering, verifying, selecting, and publishing high-rigor critical content covering international auteur cinema, contemporary world theatre, major festivals, archival restorations, dramatic literature, and critical discourse.

---

## 1. Architectural Philosophy & Layer Isolation

The core design principle of **Cinema & Theatre Review** is strict separation of concerns across deterministic data registries, evidentiary verification, editorial policy enforcement, and LLM projections.

```text
Entity Identity
      ↓
Authority Resolution
      ↓
Evidence Card (Immutable)
      ↓
Editorial Decision (Deterministic Gates & Policy)
      ↓
LLM Projection (Prompt-Injection Isolated)
```

### The Immutable Pipeline:

1. **Entity Registry (`/config/entities/`)**: Canonical registry of artists, films, plays, institutions, venues, and publications with persistent aliases, external IDs (IMDb, Wikidata, VIAF), and strict provenance records.
2. **Source Registry (`/config/sources/`)**: Catalog of primary institutions, academic journals, national theatres, trade publications, and festivals, classified into strict tiers and source classes with explicit claim-level authority scopes.
3. **Authority Map (`/config/authority_map.json`)**: Deterministic rules binding specific claim types to primary/secondary source classes, required confirmation counts, source independence policies, and conflict resolution rules.
4. **Evidence Card (`/evidence/`)**: An immutable, cryptographically hashed audit unit containing claims, categorized source evidence, entity references, authority resolutions, and conflict records.
5. **Editorial Decision Card (`/editorial/`)**: Evaluates hard gates derived from `/config/editorial_rules.json` and `/config/iran_exceptions.json`. An LLM recommendation is treated as purely advisory: deterministic policy invariants always override LLM suggestions.
6. **LLM Context Projection (`/projection/`)**: Generates bounded, sanitized views of evidence cards. Enforces a strict prompt injection boundary: untrusted source excerpts are separated from trusted structured facts, and unverified or conflicted claims are never projected as trusted truth.

---

## 2. The 14 Editorial Invariants

Defined in `/config/editorial_rules.json` and enforced across the codebase:

1. **Entity importance does not imply publication eligibility.**
2. **Source trust does not imply universal authority.**
3. **Authority is claim-specific.**
4. **Evidence is not editorial judgment.**
5. **Evidence Card is not LLM prompt.**
6. **LLM recommendation is not final decision.**
7. **Hard gates are deterministic.**
8. **Unresolved material factual conflicts normally produce HOLD.**
9. **Story state is not publication action.**
10. **Historical evidence must be auditable.**
11. **Source content is untrusted data, not instructions.**
12. **Configuration changes must be versioned.**
13. **Unknown entities must not be silently discarded.**
14. **Popularity is not a substitute for editorial value.**

---

## 3. Cryptographic Provenance & Canonical Hashing

To guarantee tamper detection, auditable decision trails, and immutable ledger integrity, the system implements deterministic canonical hashing via `/utils/canonical_hash.py`:

- **Deterministic serialization**: Lexicographically sorted object keys (`sort_keys=True`), compact separators (`separators=(',', ':')`), and unescaped UTF-8 characters (`ensure_ascii=False`).
- **Self-hash exclusion**: The hash field itself (e.g., `card_hash`, `deterministic_checksum`) is excluded from serialization to eliminate circularity.
- **SHA-256 Digest**: 64-character lowercase hexadecimal hash.

Applied automatically to:
- `EvidenceCard.integrity.card_hash`
- `EditorialDecisionCard.audit.deterministic_checksum`
- `LLMContextProjection.projection_hash`

---

## 4. Deterministic Hard Gates & Validation

Every story evaluated by `/editorial/decision_engine.py` must pass six deterministic gates:

| Gate | Identifier | Enforcement Condition |
| :--- | :--- | :--- |
| **Gate 1** | `duplicate_detection` | Fails if the story matches an existing publication record. |
| **Gate 2** | `commercial_only_filter` | Fails if the story focuses solely on box-office, merchandising, or celebrity gossip without cultural substance. |
| **Gate 3** | `iranian_daily_news_filter` | Rejects domestic Iranian entertainment news. Bypassed only when matching a verified international exception (e.g. major international festival award, Tier-1 foreign publication) via `/editorial/iran_exception_evaluator.py`. |
| **Gate 4** | `unverified_material_claims` | Fails if any material claim is unverified, lacks required authority, or has an unresolved conflict. |
| **Gate 5** | `image_provenance_requirement` | Fails if image assets lack confirmed attribution, licensing, or archive provenance. |
| **Gate 6** | `source_class_requirement` | Fails if zero sources are attached or available sources fail authority thresholds. |

---

## 5. Directory Structure

```text
├── config/                     # Core system configuration and registries
│   ├── authority_map.json      # Claim-to-source authority resolution rules
│   ├── content_taxonomy.json   # Editorial domains and recognized claim types
│   ├── editorial_rules.json    # Deterministic hard gates and character budgets
│   ├── iran_exceptions.json    # Policy criteria for Iranian international stories
│   ├── entities/               # Partitioned JSON entity registry (films, artists, etc.)
│   └── sources/                # Partitioned JSON source registry (festivals, journals, etc.)
├── editorial/                  # Editorial evaluation and decision engine
│   ├── decision_engine.py      # Core decision card generator
│   ├── decision_validator.py   # Deterministic validator enforcing policy invariants
│   ├── iran_exception_evaluator.py # Evaluates stories against Iranian coverage exceptions
│   └── rule_engine.py          # Hard gate evaluation derived from configuration
├── evidence/                   # Evidence modeling, evaluation, and validation
│   ├── authority_evaluator.py  # Evaluates confirmation counts, independence, and conflicts
│   ├── card_validator.py       # Deterministic referential integrity checks
│   ├── claim_builder.py        # Helpers for creating typed Claim objects
│   ├── evidence_builder.py     # Helpers for creating typed Evidence objects
│   └── evidence_card_builder.py# Immutable EvidenceCard assembly & hashing
├── loaders/                    # Configuration and registry loaders
│   ├── config_loader.py        # Typed loaders for JSON configuration
│   ├── cross_validator.py      # Cross-registry referential integrity runner
│   ├── entity_loader.py        # Entity registry loader with duplicate checks
│   └── source_loader.py        # Source registry loader with duplicate checks
├── projection/                 # LLM context generation
│   └── llm_context.py          # Prompt injection boundary & bounded projection builder
├── schemas/                    # Pydantic v2 strict schemas (extra='forbid')
│   ├── authority_map.py
│   ├── context_projection.py
│   ├── decision_card.py
│   ├── editorial_rules.py
│   ├── entity_registry.py
│   ├── evidence_card.py
│   ├── iran_exceptions.py
│   └── source_registry.py
├── tests/                      # Pytest regression suite
└── utils/
    └── canonical_hash.py       # Deterministic canonical hashing (RFC 8785 style)
```

---

## 6. Running Validation & Tests

### Cross-Registry Validation Runner
Validates JSON configuration, schema integrity, entity references, and source authority claim references across all registries:

```bash
python3 -m loaders.cross_validator
```

### Running Test Suite
Runs the comprehensive regression test suite covering canonical hashing, immutable cards, authority evaluations, gate enforcement, story action mapping, and prompt-injection boundaries:

```bash
pytest -v
```


## Public release scope

This repository distributes the open-source Data & Editorial Core of
Cinema & Theatre Review. It includes canonical source/entity registries,
evidence models, deterministic editorial rules, validation, bounded LLM
context projection, and the associated core regression tests.

Production publishing integrations, Telegram destinations, deployment
automation, live operational state, generated acquisition telemetry,
private credentials, and the separate React/Vite application shell are
intentionally excluded from this release.

The excluded production components are not required to install or validate
this core distribution. Do not place API keys, private channel identifiers,
or production state files in this repository.
