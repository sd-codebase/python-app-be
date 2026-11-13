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


def test_no_chapter_ids_is_original_behaviour():
    # only 10 L1 questions exist: original behaviour returns 10, no top-up
    got = select_questions_for_section(POOL, sec(15))
    assert len(got) == 10 and all(x["level"] == 1 for x in got)


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
