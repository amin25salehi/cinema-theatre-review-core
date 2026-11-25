"""
Editorial Rule Engine - Cinema & Theatre Review Editorial OS v1.0.1
Evaluates deterministic hard gates, editorial signals, and format budgets.
Configuration files serve as the source of truth for policies, weights, and budgets.
"""

from datetime import datetime, timezone
from typing import Any

from schemas.decision_card import (
    EditorialSignals,
    GateResult,
    GateStatus,
    HardGatesEvaluation,
)
from schemas.editorial_rules import EditorialRules
from schemas.entity_registry import EntityProfile
from schemas.evidence_card import (
    AuthorityStatus,
    ClaimStatus,
    ConflictStatus,
    EvidenceCard,
    ImageOfficiality,
)


class EditorialRuleEngine:
    def __init__(
        self,
        editorial_rules: dict[str, Any] | EditorialRules,
        iran_exceptions: dict[str, Any],
        entities: dict[str, EntityProfile],
    ):
        if isinstance(editorial_rules, EditorialRules):
            self.editorial_rules = editorial_rules.model_dump()
        else:
            self.editorial_rules = editorial_rules
        self.iran_exceptions = iran_exceptions
        self.entities = entities

    def evaluate_hard_gates(
        self,
        card: EvidenceCard,
        is_duplicate: bool = False,
        is_commercial_only: bool = False,
        is_iranian_daily_news: bool = False,
        iran_exception_matched: str | None = None,
        evaluated_at: str | None = None,
    ) -> HardGatesEvaluation:
        now_iso = evaluated_at or datetime.now(timezone.utc).isoformat()
        hard_gates_cfg = self.editorial_rules.get("hard_gates", {})

        # Gate 1: Duplicate
        dup_cfg = hard_gates_cfg.get("duplicate_detection", {"enabled": True})
        if dup_cfg.get("enabled", True):
            if is_duplicate:
                dup_result = GateResult(
                    status=GateStatus.FAIL,
                    reason="Story is an exact or near-identical duplicate of an existing publication.",
                    checked_at=now_iso,
                )
            else:
                dup_result = GateResult(
                    status=GateStatus.PASS_,
                    reason="Duplicate check passed.",
                    checked_at=now_iso,
                )
        else:
            dup_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Duplicate detection gate disabled in policy.",
                checked_at=now_iso,
            )

        # Gate 2: Commercial Only
        comm_cfg = hard_gates_cfg.get("commercial_only_filter") or hard_gates_cfg.get(
            "commercial_only_filtering", {"enabled": True}
        )
        if comm_cfg.get("enabled", True):
            if is_commercial_only:
                comm_result = GateResult(
                    status=GateStatus.FAIL,
                    reason="Story is purely commercial / box office / celebrity merchandising without cultural significance.",
                    checked_at=now_iso,
                )
            else:
                comm_result = GateResult(
                    status=GateStatus.PASS_,
                    reason="Editorial significance check passed.",
                    checked_at=now_iso,
                )
        else:
            comm_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Commercial filtering gate disabled in policy.",
                checked_at=now_iso,
            )

        # Gate 3: Iranian Daily News
        iran_cfg = hard_gates_cfg.get("iranian_daily_news_filter") or hard_gates_cfg.get(
            "iranian_cinema_coverage", {"enabled": True}
        )
        if iran_cfg.get("enabled", True):
            if is_iranian_daily_news:
                if iran_exception_matched:
                    # Valid exception passes gate!
                    iran_result = GateResult(
                        status=GateStatus.PASS_,
                        reason=f"Iranian subject qualifies under verified international exception: '{iran_exception_matched}'.",
                        checked_at=now_iso,
                    )
                else:
                    iran_result = GateResult(
                        status=GateStatus.FAIL,
                        reason="Iranian domestic daily cinema news is excluded by editorial policy without a qualified international exception.",
                        checked_at=now_iso,
                    )
            else:
                iran_result = GateResult(
                    status=GateStatus.PASS_,
                    reason="International scope confirmed.",
                    checked_at=now_iso,
                )
        else:
            iran_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Iranian coverage gate disabled in policy.",
                checked_at=now_iso,
            )

        # Gate 4: Unverified Material Claims
        claim_cfg = hard_gates_cfg.get("unverified_material_claims") or hard_gates_cfg.get(
            "claim_verification_requirement", {"enabled": True}
        )
        if claim_cfg.get("enabled", True):
            material_claims = [c for c in card.claims if c.material and c.verification_required]
            unverified = [c for c in material_claims if c.status != ClaimStatus.SUPPORTED]
            conflicted_auth = [
                ar for ar in card.authority_resolution
                if ar.status in (AuthorityStatus.CONFLICTED, AuthorityStatus.INSUFFICIENT)
            ]
            unresolved_conflicts = [
                conf for conf in card.conflicts
                if conf.status == ConflictStatus.UNRESOLVED
            ]

            if unverified or conflicted_auth or unresolved_conflicts:
                reasons = []
                if unverified:
                    reasons.append(f"{len(unverified)} material claim(s) unverified ({[c.claim_id for c in unverified]})")
                if conflicted_auth:
                    reasons.append(f"{len(conflicted_auth)} claim(s) have conflicted or insufficient authority")
                if unresolved_conflicts:
                    reasons.append(f"{len(unresolved_conflicts)} unresolved conflict(s)")
                claim_result = GateResult(
                    status=GateStatus.FAIL,
                    reason="; ".join(reasons),
                    checked_at=now_iso,
                )
            else:
                claim_result = GateResult(
                    status=GateStatus.PASS_,
                    reason=f"All {len(material_claims)} material claims verified with authoritative evidence.",
                    checked_at=now_iso,
                )
        else:
            claim_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Claim verification gate disabled in policy.",
                checked_at=now_iso,
            )

        # Gate 5: Image Provenance
        img_cfg = hard_gates_cfg.get("image_provenance_requirement") or hard_gates_cfg.get(
            "image_provenance_verification", {"enabled": True}
        )
        if img_cfg.get("enabled", True):
            if card.image_evidence:
                rejected_or_unknown = [
                    img for img in card.image_evidence
                    if img.officiality_status in (ImageOfficiality.REJECTED, ImageOfficiality.UNKNOWN)
                ]
                if rejected_or_unknown:
                    img_result = GateResult(
                        status=GateStatus.FAIL,
                        reason=f"Contains {len(rejected_or_unknown)} image(s) with unconfirmed or rejected provenance.",
                        checked_at=now_iso,
                    )
                else:
                    img_result = GateResult(
                        status=GateStatus.PASS_,
                        reason="All attached images verified with confirmed or likely official provenance.",
                        checked_at=now_iso,
                    )
            else:
                img_result = GateResult(
                    status=GateStatus.NOT_APPLICABLE,
                    reason="No images associated with this evidence card.",
                    checked_at=now_iso,
                )
        else:
            img_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Image provenance gate disabled in policy.",
                checked_at=now_iso,
            )

        # Gate 6: Source Requirement (Policy-Driven)
        # Invariant: Never hard-code source_count > 0 as universal pass condition.
        # Must enforce minimum confirmations from authority resolution.
        source_cfg = hard_gates_cfg.get("source_class_requirement", {"enabled": True})
        if source_cfg.get("enabled", True):
            if card.integrity.source_count == 0:
                source_result = GateResult(
                    status=GateStatus.FAIL,
                    reason="Zero sources provided.",
                    checked_at=now_iso,
                )
            else:
                # Check whether all material claims requiring verification have achieved
                # CONFIRMED or SECONDARY_CONFIRMED authority status
                material_claims = [c for c in card.claims if c.material and c.verification_required]
                auth_statuses = {ar.claim_id: ar.status for ar in card.authority_resolution}

                unmet_authority_claims = [
                    c.claim_id for c in material_claims
                    if auth_statuses.get(c.claim_id) not in (
                        AuthorityStatus.CONFIRMED,
                        AuthorityStatus.SECONDARY_CONFIRMED,
                    )
                ]

                if unmet_authority_claims:
                    source_result = GateResult(
                        status=GateStatus.FAIL,
                        reason=(
                            f"Source requirement failed: Material claim(s) {unmet_authority_claims} do not meet "
                            f"minimum confirmation requirements (require authoritative primary source or sufficient "
                            f"independent secondary sources per policy; discovery-only sources cannot satisfy verification)."
                        ),
                        checked_at=now_iso,
                    )
                else:
                    source_result = GateResult(
                        status=GateStatus.PASS_,
                        reason=(
                            f"Source requirement satisfied: {card.integrity.source_count} source(s) from "
                            f"{card.integrity.independent_source_count} independent domain(s) satisfying policy."
                        ),
                        checked_at=now_iso,
                    )
        else:
            source_result = GateResult(
                status=GateStatus.NOT_APPLICABLE,
                reason="Source requirement gate disabled in policy.",
                checked_at=now_iso,
            )

        return HardGatesEvaluation(
            duplicate=dup_result,
            commercial_only=comm_result,
            iranian_daily_news=iran_result,
            unverified_claim=claim_result,
            image_provenance=img_result,
            source_requirement=source_result,
        )

    def calculate_signals(
        self, card: EvidenceCard, iran_exception_matched: str | None = None
    ) -> EditorialSignals:
        """
        Calculates editorial signals using deterministic criteria and configured signal weights.
        NOTE: Scoring formulas represent initial heuristic calibration and will be refined
        during the editorial operations calibration phase.
        """
        # Check referenced entities
        has_reference = False
        has_emerging = False
        for entity_ref in card.entities:
            ent = self.entities.get(entity_ref.entity_id)
            if ent:
                if ent.status.value == "reference":
                    has_reference = True
                elif ent.status.value == "emerging":
                    has_emerging = True

        # Check claim types
        major_fest = any(c.claim_type == "festival_selection" for c in card.claims)
        major_awd = any(c.claim_type == "award_conferral" for c in card.claims)
        archival_sig = any(c.claim_type == "archival_restoration" for c in card.claims)
        crit_attention = any(c.claim_type == "critical_assessment" for c in card.claims)
        book_sig = any(c.claim_type == "book_publication_date" for c in card.claims)
        play_sig = any(c.claim_type == "theatre_premiere" for c in card.claims)

        # Compute evidence strength
        total_claims = len(card.claims)
        supported_claims = sum(1 for c in card.claims if c.status == ClaimStatus.SUPPORTED)
        evidence_strength = (supported_claims / total_claims) if total_claims > 0 else 0.0

        # Deterministic recency heuristic based on publication timestamps
        recency = 0.85  # Documented baseline heuristic
        pub_timestamps: list[datetime] = []
        for ev in card.evidence:
            if ev.published_at:
                try:
                    dt = datetime.fromisoformat(ev.published_at.replace("Z", "+00:00"))
                    pub_timestamps.append(dt)
                except ValueError:
                    pass

        if pub_timestamps:
            latest_pub = max(pub_timestamps)
            now = datetime.now(timezone.utc)
            delta_hours = (now - latest_pub).total_seconds() / 3600.0
            if delta_hours <= 24:
                recency = 1.0
            elif delta_hours <= 72:
                recency = 0.90
            elif delta_hours <= 168:  # 7 days
                recency = 0.75
            else:
                recency = 0.50

        # Editorial fit heuristic (uncalibrated baseline)
        editorial_fit = 0.50
        if has_reference:
            editorial_fit += 0.25
        if major_fest or major_awd or archival_sig or book_sig or play_sig:
            editorial_fit += 0.25
        editorial_fit = min(1.0, editorial_fit)

        return EditorialSignals(
            evidence_strength=round(evidence_strength, 2),
            editorial_fit=round(editorial_fit, 2),
            recency=round(recency, 2),
            major_festival=major_fest,
            major_award=major_awd,
            major_retrospective=False,
            restoration=archival_sig,
            archival_significance=archival_sig,
            academic_significance=crit_attention,
            important_book=book_sig,
            important_play=play_sig,
            reference_entity=has_reference,
            emerging_entity=has_emerging,
            independent_critical_attention=crit_attention,
            iran_exception=bool(iran_exception_matched),
        )
