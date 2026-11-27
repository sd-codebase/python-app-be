"""Run with pytest, or:  python -m tests.test_section_pool"""
from app.routes.tests import select_questions_for_section


def q(i, ch, level):
    return {"id": f"{ch}-{i}", "chapter_id": ch, "level": level, "has_integer_answer": None}


POOL = [q(i, "A", 1) for i in range(10)] + [q(i, "B", 2) for i in range(10)] + [q(i, "C", 3) for i in range(2)]


def sec(n, chapters=None, diff=None):
    s = {"question_count": n, "difficulty": diff or {"L1": n, "L2": 0, "L3": 0}}
    if chapters is not None:
        s["chapter_ids"] = chapters
    return s


def test_no_chapter_ids_short_level_is_filled():
    # only 10 L1 questions exist: all 10 L1 are used and the shortfall (5) is filled from other levels
    got = select_questions_for_section(POOL, sec(15))
    assert len(got) == 15 and len({x["id"] for x in got}) == 15
    assert sum(1 for x in got if x["level"] == 1) == 10


def test_chapter_pool_restricts_chapters():
    got = select_questions_for_section(POOL, sec(4, ["B"], {"L1": 0, "L2": 4, "L3": 0}))
    assert len(got) == 4 and {x["chapter_id"] for x in got} == {"B"}


def test_chapter_pool_tops_up_short_level():
    # pool B+C has only 2 L3 questions; asking 5 L3 must still give 5 from B/C
    got = select_questions_for_section(POOL, sec(5, ["B", "C"], {"L1": 0, "L2": 0, "L3": 5}))
    assert len(got) == 5
    assert {x["chapter_id"] for x in got} <= {"B", "C"}
    assert len({x["id"] for x in got}) == 5


def test_pool_smaller_than_request():
    got = select_questions_for_section(POOL, sec(5, ["C"], {"L1": 2, "L2": 2, "L3": 1}))
    assert len(got) == 2  # only 2 questions exist in chapter C


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)


def test_difficulty_shortfall_is_filled_from_other_levels():
    from app.routes.tests import select_questions_by_difficulty
    pool = [{"id": f"a{i}", "level": 1} for i in range(8)] + [{"id": "b0", "level": 2}]
    sel = select_questions_by_difficulty(pool, {"L1": 2, "L2": 3, "L3": 2})
    assert len(sel) == 7 and len({q["id"] for q in sel}) == 7


def test_difficulty_shortfall_never_exceeds_pool():
    from app.routes.tests import select_questions_by_difficulty
    pool = [{"id": "x", "level": 3}, {"id": "y", "level": 1}]
    sel = select_questions_by_difficulty(pool, {"L1": 5, "L2": 5, "L3": 5})
    assert len(sel) == 2
