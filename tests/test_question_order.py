"""Run with pytest, or:  python -m tests.test_question_order"""
from app.utils.question_order import order_like_paper


def q(i, t=None, num=False, para=None):
    return {"id": i, "type": t, "has_integer_answer": num, "paragraph_id": para}


def ids(qs):
    return [x["id"] for x in qs]


def test_untyped_unchanged():
    qs = [q("3", num=True), q("1"), q("2", num=True)]
    assert order_like_paper(qs) is qs


def test_paper_order():
    qs = [
        q("tf", "True/False"), q("match", "Match the Column"), q("num", "Numerical Types/Integer Types", True),
        q("multi", "Multiple Correct"), q("ar", "Assertion Reason/Statement Based"), q("single", "Single Correct"),
        q("fill", "Fill in the Blanks", True),
    ]
    assert ids(order_like_paper(qs)) == ["single", "ar", "multi", "num", "fill", "match", "tf"]


def test_passage_siblings_together_and_numeric_comprehension_in_c():
    qs = [
        q("c1", "Comprehension Based/Passage Based", para="P1"), q("s", "Single Correct"),
        q("c2", "Comprehension Based/Passage Based", para="P2"), q("c3", "Comprehension Based/Passage Based", para="P1"),
        q("cn", "Comprehension Based/Passage Based", True, para="P3"), q("n", "Numerical Types/Integer Types", True),
    ]
    assert ids(order_like_paper(qs)) == ["s", "c1", "c3", "c2", "n", "cn"]


def test_stable_within_same_type():
    qs = [q("b", "Single Correct"), q("a", "Single Correct"), q("c", "Single Correct")]
    assert ids(order_like_paper(qs)) == ["b", "a", "c"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
