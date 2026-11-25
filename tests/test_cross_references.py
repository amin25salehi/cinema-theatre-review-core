"""
Unit Tests - Cross Registry References
Verifies that loaders detect foreign-key violations and invalid references.
"""

from loaders.cross_validator import CrossRegistryValidator


def test_cross_registry_validation_passes_on_bootstrap_config():
    validator = CrossRegistryValidator()
    is_valid, errors, stats = validator.validate_all()
    assert is_valid is True, f"Cross-validation failed with errors: {errors}"
    assert len(errors) == 0
    assert stats["sources_count"] > 10
    assert stats["entities_count"] > 10
    assert stats["authority_rules_count"] >= 8
