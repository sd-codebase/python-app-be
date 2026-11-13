"""Chapter-pool support for test sections.

A section may carry ``chapter_ids``: the section then draws only from those
chapters (e.g. "3 questions from this group of 5 chapters"). Sections without
``chapter_ids`` behave exactly as before.
"""
import random
from typing import List


def filter_by_chapters(questions: List[dict], section: dict) -> List[dict]:
    """Keep only questions from the section's chapter pool (no-op when unset)."""
    chapter_ids = section.get("chapter_ids")
    if not chapter_ids:
        return questions
    allowed = set(chapter_ids)
    return [q for q in questions if q.get("chapter_id") in allowed]


def section_target(section: dict) -> int:
    """Number of questions the section asks for."""
    difficulty = section.get("difficulty") or {}
    total = sum(v for v in difficulty.values() if isinstance(v, int))
    return total if total > 0 else int(section.get("question_count") or 0)


def top_up(selected: List[dict], pool: List[dict], section: dict) -> List[dict]:
    """For chapter-pool sections only: if a difficulty level ran short inside a
    small pool, fill the gap from the pool's other questions (any level) so the
    section still gets its full count."""
    if not section.get("chapter_ids"):
        return selected
    need = section_target(section) - len(selected)
    if need <= 0:
        return selected
    used = {q.get("id") for q in selected}
    rest = [q for q in pool if q.get("id") not in used]
    return selected + random.sample(rest, min(need, len(rest)))
