"""
Order the questions of a generated JEE Advanced test like the real paper:

    A  single-answer:   Single Correct, Assertion Reason, Comprehension (letter answer)
    B  Multiple Correct
    C  numerical:       Numerical/Integer, Fill in the Blanks, Comprehension (numeric answer)
    D  Match the Column
    E  anything else (e.g. True/False)

Inside a group, questions of the same type stay together, and questions that share a
passage (paragraph_id) sit next to each other.

NEET / JEE Main questions have no `type`; for them the list is returned unchanged, so
their tests keep the order they had before.
"""

from typing import List

_SINGLE_TYPES = ["Single Correct", "Assertion Reason/Statement Based", "Comprehension Based/Passage Based"]
_NUMERIC_TYPES = ["Numerical Types/Integer Types", "Fill in the Blanks", "Comprehension Based/Passage Based"]


def _sort_key(indexed):
    position, q = indexed
    qtype = q.get("type") or ""
    if q.get("has_integer_answer"):
        group, sub = 2, _NUMERIC_TYPES.index(qtype) if qtype in _NUMERIC_TYPES else len(_NUMERIC_TYPES)
    elif qtype in _SINGLE_TYPES:
        group, sub = 0, _SINGLE_TYPES.index(qtype)
    elif qtype == "Multiple Correct":
        group, sub = 1, 0
    elif qtype == "Match the Column":
        group, sub = 3, 0
    else:
        group, sub = 4, 0
    # Keep passage siblings together; otherwise keep the (random) selection order.
    return (group, sub, q.get("paragraph_id") or "", position)


def order_like_paper(questions: List[dict]) -> List[dict]:
    """Return the questions in A/B/C/D/E order (JEE Advanced only; see module doc)."""
    if not any(q.get("type") for q in questions):
        return questions
    return [q for _, q in sorted(enumerate(questions), key=_sort_key)]
