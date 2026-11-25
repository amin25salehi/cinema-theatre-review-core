"""
Stage 8: Human Editorial Review Queue & State Manager.
Cinema & Theatre Review Editorial OS.

Manages the editorial staging state in data/editorial_review_queue.json:
- Maintains daily conductor slots (1 to 15) with flexible distribution.
- Assigns and displays Quality Tiers:
    * Level A: Ready for review (آماده بازبینی)
    * Level B: Needs editor attention (نیازمند توجه سردبیر) with advisory warnings
    * Level C: Defect or unverified quote (دارای نقص)
- Supports Chief Editor actions:
    * approve_post(slot)
    * edit_post(slot, text, topic, image)
    * reject_post(slot, replacement_candidate)
    * publish_approved_to_telegram(slot, target_channel)
- Syncs state with src/data/liveCuratedPosts.json for the React frontend dashboard.
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

REVIEW_QUEUE_FILE = "data/editorial_review_queue.json"
LIVE_CURATED_POSTS_FILE = "src/data/liveCuratedPosts.json"

class EditorialReviewQueue:
    def __init__(self, queue_file: str = REVIEW_QUEUE_FILE):
        self.queue_file = queue_file
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "version": "2.0.0",
            "last_updated": None,
            "target_daily_slots": 15,
            "stats": {
                "total_staged": 0,
                "tier_a_ready": 0,
                "tier_b_attention": 0,
                "tier_c_defect": 0,
                "approved_count": 0,
                "dispatched_count": 0
            },
            "slots": {}
        }

    def load_state(self) -> Dict[str, Any]:
        self.state = self._load_state()
        return self.state

    def _save_state(self):
        with open(self.queue_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
        # Mirror to frontend src/data/liveCuratedPosts.json
        self._mirror_to_frontend()

    def _mirror_to_frontend(self):
        try:
            os.makedirs(os.path.dirname(LIVE_CURATED_POSTS_FILE), exist_ok=True)
            staged_posts = list(self.state.get("slots", {}).values())
            # Sort by slot
            staged_posts.sort(key=lambda x: x.get("slot", 99))

            slot_map = {
                1: 'iranian_indie',
                2: 'world_documentary',
                3: 'film_theory_essay',
                4: 'european_auteur',
                5: 'american_indie',
                6: 'asian_mastery',
                7: 'world_documentary',
                8: 'progressive_theatre',
                9: 'progressive_theatre',
                10: 'soundscape_aesthetics',
                11: 'world_documentary',
                12: 'film_theory_essay',
                13: 'archive_restoration',
                14: 'film_theory_essay',
                15: 'nightly_cinephilia'
            }

            mapped_posts = []
            for p in staged_posts:
                text_lines = [l.strip() for l in (p.get("text") or "").split("\n") if l.strip()]
                headline = text_lines[0] if text_lines else p.get("topic") or f"اسلات {p.get('slot')}"
                lead = text_lines[1] if len(text_lines) > 1 else ""
                body = p.get("text") or ""
                image_url = p.get("image_source_url") or p.get("image_file") or "https://images.unsplash.com/photo-1489599849927-2ee91cede3ba?auto=format&fit=crop&w=1200&q=80"
                slot_id = p.get("slot", 1)
                conductor_slot_key = slot_map.get(slot_id, 'iranian_indie')
                tier = p.get("quality_tier", "B")

                mapped_posts.append({
                    "id": f"live-slot-{slot_id}",
                    "candidate_id": p.get("candidate_id", f"cand-{slot_id}"),
                    "original_title": p.get("original_title", p.get("topic", "")),
                    "author": p.get("author"),
                    "topic": p.get("topic", ""),
                    "category": p.get("category", "cinema"),
                    "content_type": p.get("content_type", "review"),
                    "editorial_selection_reason": p.get("editorial_selection_reason", "انتخاب بر اساس اولویت کنداکتور تحریریه و اصالت فرم"),
                    "conductorSlot": conductor_slot_key,
                    "conductorSlotNameFa": p.get("name", f"اسلات {slot_id}"),
                    "headline": headline,
                    "lead": lead,
                    "body": body,
                    "original_summary": p.get("original_summary", ""),
                    "imageUrl": image_url,
                    "imageCaption": p.get("topic", ""),
                    "imageCredit": p.get("image_credit", "آرشیو موثق تحریریه"),
                    "sourceName": p.get("source_name", "Cinema & Theatre Review"),
                    "sourceUrl": p.get("original_url", "https://t.me/cinema_theatre_review"),
                    "sourceTier": 1,
                    "hashtags": [f"#{p.get('name', '').replace(' ', '_')}"],
                    "status": "ready_for_review" if p.get("review_status") in ("PENDING_EDITOR_REVIEW", "ready_for_review") else "approved" if p.get("review_status") in ("APPROVED", "approved") else "scheduled" if p.get("review_status") in ("SCHEDULED", "scheduled") else "published" if p.get("review_status") in ("DISPATCHED", "published") else "rejected" if p.get("review_status") in ("REJECTED", "rejected") else p.get("review_status", "ready_for_review"),
                    "charCount": len(body),
                    "qualityTier": f"LEVEL_{tier}",
                    "qualityTierLabel": "سطح A (آماده بازبینی)" if tier == "A" else "سطح B (نیازمند توجه سردبیر)" if tier == "B" else "سطح C (بازیابی از نقص)",
                    "advisoryWarnings": p.get("advisory_warnings", []),
                    "sourcePublicationDate": (p.get("temporal_model") or {}).get("source_publication_date"),
                    "retrieved_at": (p.get("temporal_model") or {}).get("retrieved_at") or p.get("retrieved_at"),
                    "eventDate": (p.get("temporal_model") or {}).get("event_date"),
                    "workCreationYear": (p.get("temporal_model") or {}).get("work_creation_year"),
                    "imageProvenance": p.get("image_credit", ""),
                    "imageMode": "text_only" if p.get("image_mode") == "TEXT_ONLY" else "photo",
                    "editorialScore": p.get("editorial_score", 85)
                })

            frontend_payload = {
                "updated_at": self.state.get("last_updated"),
                "total_posts": len(mapped_posts),
                "stats": self.state.get("stats", {}),
                "daily_posts": mapped_posts
            }
            with open(LIVE_CURATED_POSTS_FILE, "w", encoding="utf-8") as f:
                json.dump(frontend_payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to mirror to frontend: {e}")

    def stage_daily_slots(self, posts: List[Dict[str, Any]], preserve_approved: bool = True) -> Dict[str, Any]:
        """Loads or updates the 15 daily conductor slots into the review queue."""
        now_iso = datetime.now(timezone.utc).isoformat()

        for p in posts:
            slot = p.get("slot")
            if not slot:
                continue
            slot_key = str(slot)

            # Preserve human editor decisions if slot is approved, scheduled, or published
            if preserve_approved and slot_key in self.state.get("slots", {}):
                existing_st = self.state["slots"][slot_key].get("review_status", "").lower()
                if existing_st in ("approved", "scheduled", "published"):
                    continue

            tier = p.get("quality_tier", "A")
            status = p.get("review_status", "PENDING_EDITOR_REVIEW")

            self.state["slots"][slot_key] = {
                "slot": slot,
                "candidate_id": p.get("candidate_id", f"cand-{slot}"),
                "original_title": p.get("original_title", p.get("topic", "")),
                "author": p.get("author"),
                "scheduled_tehran_time": p.get("scheduled_tehran_time", f"{7 + slot:02d}:00"),
                "name": p.get("name", f"اسلات {slot}"),
                "category": p.get("category", "cinema"),
                "content_type": p.get("content_type", "review"),
                "editorial_selection_reason": p.get("editorial_selection_reason", ""),
                "topic": p.get("topic", ""),
                "text": p.get("text", ""),
                "original_summary": p.get("original_summary", ""),
                "quality_tier": tier,
                "quality_status": p.get("quality_status", "READY_FOR_REVIEW"),
                "advisory_warnings": p.get("advisory_warnings", []),
                "review_status": status,
                "image_file": p.get("image_file"),
                "image_credit": p.get("image_credit"),
                "image_source_url": p.get("image_source_url"),
                "image_mode": p.get("image_mode", "PHOTO" if p.get("image_file") else "TEXT_ONLY"),
                "source_name": p.get("source_name", "Editorial Collective"),
                "original_url": p.get("original_url", ""),
                "source_publication_date": (p.get("temporal_model") or {}).get("source_publication_date"),
                "retrieved_at": (p.get("temporal_model") or {}).get("retrieved_at") or p.get("retrieved_at", now_iso),
                "temporal_model": p.get("temporal_model", {}),
                "created_at": p.get("created_at", now_iso),
                "editor_notes": p.get("editor_notes", "")
            }

        self.state["last_updated"] = now_iso
        self._recalculate_stats()
        self._save_state()
        return self.state["stats"]

    def approve_slot(self, slot: int, notes: str = "") -> bool:
        slot_key = str(slot)
        if slot_key in self.state["slots"]:
            self.state["slots"][slot_key]["review_status"] = "APPROVED"
            self.state["slots"][slot_key]["editor_notes"] = notes
            self.state["slots"][slot_key]["approved_at"] = datetime.now(timezone.utc).isoformat()
            self._recalculate_stats()
            self._save_state()
            return True
        return False

    def reject_slot(self, slot: int, reason: str = "") -> bool:
        slot_key = str(slot)
        if slot_key in self.state["slots"]:
            self.state["slots"][slot_key]["review_status"] = "REJECTED"
            self.state["slots"][slot_key]["editor_notes"] = reason
            self.state["slots"][slot_key]["rejected_at"] = datetime.now(timezone.utc).isoformat()
            self._recalculate_stats()
            self._save_state()
            return True
        return False

    def schedule_slot(self, slot: int, scheduled_time: Optional[str] = None) -> bool:
        slot_key = str(slot)
        if slot_key in self.state["slots"]:
            self.state["slots"][slot_key]["review_status"] = "SCHEDULED"
            if scheduled_time:
                self.state["slots"][slot_key]["scheduled_tehran_time"] = scheduled_time
            self.state["slots"][slot_key]["scheduled_at"] = datetime.now(timezone.utc).isoformat()
            self._recalculate_stats()
            self._save_state()
            return True
        return False

    def publish_slot(self, slot: int, telegram_msg_id: Optional[int] = None) -> bool:
        slot_key = str(slot)
        if slot_key in self.state["slots"]:
            self.state["slots"][slot_key]["review_status"] = "DISPATCHED"
            self.state["slots"][slot_key]["telegram_msg_id"] = telegram_msg_id
            self.state["slots"][slot_key]["published_at"] = datetime.now(timezone.utc).isoformat()
            self._recalculate_stats()
            self._save_state()
            return True
        return False
    def update_slot_status(self, slot: int, new_status: str, editor_notes: str = "") -> bool:
        slot_key = str(slot)
        if slot_key not in self.state["slots"]:
            return False
        normalized_status = new_status.lower()
        if normalized_status in ("approved", "approve"):
            return self.approve_slot(slot, notes=editor_notes)
        elif normalized_status in ("rejected", "reject"):
            return self.reject_slot(slot, reason=editor_notes)
        elif normalized_status in ("scheduled", "schedule"):
            return self.schedule_slot(slot)
        elif normalized_status in ("published", "dispatched"):
            return self.publish_slot(slot)
        elif normalized_status in ("ready_for_review", "reset", "pending_editor_review"):
            self.state["slots"][slot_key]["review_status"] = "ready_for_review"
            self.state["slots"][slot_key]["editor_notes"] = editor_notes
            self._recalculate_stats()
            self._save_state()
            return True
        return False

    def _recalculate_stats(self):
        ready = approved = rejected = scheduled = published = 0
        tier_a = tier_b = tier_c = 0
        for p in self.state["slots"].values():
            st = p.get("review_status", "").lower()
            if st in ("ready_for_review", "pending_editor_review"):
                ready += 1
            elif st == "approved":
                approved += 1
            elif st == "rejected":
                rejected += 1
            elif st == "scheduled":
                scheduled += 1
            elif st in ("published", "dispatched"):
                published += 1

            tier = p.get("quality_tier", "A")
            if tier == "A":
                tier_a += 1
            elif tier == "B":
                tier_b += 1
            else:
                tier_c += 1

        self.state["stats"]["total_staged"] = len(self.state["slots"])
        self.state["stats"]["tier_a_ready"] = tier_a
        self.state["stats"]["tier_b_attention"] = tier_b
        self.state["stats"]["tier_c_defect"] = tier_c
        self.state["stats"]["ready_for_review_count"] = ready
        self.state["stats"]["approved_count"] = approved
        self.state["stats"]["rejected_count"] = rejected
        self.state["stats"]["scheduled_count"] = scheduled
        self.state["stats"]["published_count"] = published

    def mark_dispatched(self, slot: int, telegram_msg_id: Optional[int] = None) -> bool:
        return self.publish_slot(slot, telegram_msg_id)

    def edit_slot(self, slot: int, new_topic: Optional[str] = None, new_text: Optional[str] = None, new_image_file: Optional[str] = None) -> bool:
        slot_key = str(slot)
        if slot_key in self.state["slots"]:
            if new_topic is not None:
                self.state["slots"][slot_key]["topic"] = new_topic
            if new_text is not None:
                self.state["slots"][slot_key]["text"] = new_text
            if new_image_file is not None:
                self.state["slots"][slot_key]["image_file"] = new_image_file
                self.state["slots"][slot_key]["image_mode"] = "PHOTO" if new_image_file else "TEXT_ONLY"
            self.state["slots"][slot_key]["edited_at"] = datetime.now(timezone.utc).isoformat()
            self._save_state()
            return True
        return False

    def get_slot(self, slot: int) -> Optional[Dict[str, Any]]:
        return self.state.get("slots", {}).get(str(slot))

    def get_all_slots(self) -> List[Dict[str, Any]]:
        slots = list(self.state.get("slots", {}).values())
        slots.sort(key=lambda x: x.get("slot", 99))
        return slots
