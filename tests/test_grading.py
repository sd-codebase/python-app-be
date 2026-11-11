"""Tests for app.utils.grading.

Run with pytest, or without it:  python -m tests.test_grading
"""
import itertools

from app.utils.grading import (
    answers_match,
    score_question,
    SCORING_JEE_ADV_MULTI,
    STATUS_CORRECT,
    STATUS_PARTIAL,
    STATUS_WRONG,
    STATUS_UNANSWERED,
)

MULTI = "Multiple Correct"


# ---------------------------------------------------------------------------
# NEET / JEE Main: no type, no scoring -> must equal the original inline rule
# ---------------------------------------------------------------------------
def _either_option(user, correct):
    """Keys like "b,d" (NTA accepted either option): one listed option is correct."""
    return (user is not None and correct is not None and "," in correct and "," not in user
            and user.strip() != "" and user.strip().lower() in [c.strip().lower() for c in correct.split(",")])


def _original(user, correct, marks, negative):
    is_correct = user is not None and (user == correct or _either_option(user, correct))
    if is_correct:
        return marks, STATUS_CORRECT
    if user is not None and user != "":
        return -negative, STATUS_WRONG
    return 0.0, STATUS_UNANSWERED


def test_untyped_matches_original_rule_exhaustively():
    values = [None, "", " ", "a", "A", "b", "a, c", "c, a", "4", "4.0", "True", "TRUE"]
    for user, correct in itertools.product(values, repeat=2):
        for marks, negative in [(4, 1), (4, 0), (3, 1)]:
            got = score_question(user, correct, marks, negative)
            assert got == _original(user, correct, float(marks), float(negative)), (user, correct, got)
            assert answers_match(user, correct) == (user is not None and (user == correct or _either_option(user, correct)))


def test_untyped_two_option_key_accepts_either():
    assert answers_match("b", "b,d")
    assert answers_match("d", "b, d")
    assert not answers_match("a", "b,d")
    assert not answers_match("", "b,d")
    assert score_question("d", "b,d", 4, 1) == (4.0, STATUS_CORRECT)
    assert score_question("a", "b,d", 4, 1) == (-1.0, STATUS_WRONG)


# ---------------------------------------------------------------------------
# JEE Advanced matching
# ---------------------------------------------------------------------------
def test_true_false_case_insensitive():
    assert answers_match("True", "TRUE", "True/False")
    assert answers_match("false", "False", "True/False")
    assert not answers_match("True", "False", "True/False")


def test_multiple_correct_order_and_format_insensitive():
    assert answers_match("c,a", "a, c", MULTI)
    assert answers_match("A C", "a, c", MULTI)
    assert not answers_match("a", "a, c", MULTI)


def test_numerical_compares_as_numbers():
    assert answers_match("0.50", "0.5", "Numerical Types/Integer Types", True)
    assert answers_match("6", "6.0", "Numerical Types/Integer Types", True)
    assert not answers_match("6.1", "6", "Numerical Types/Integer Types", True)


def test_single_letter_types_case_insensitive():
    for t in ["Single Correct", "Match the Column", "Assertion Reason/Statement Based",
              "Comprehension Based/Passage Based"]:
        assert answers_match("B", "b", t)
        assert not answers_match("a", "b", t)


def test_typed_blank_never_correct():
    assert not answers_match("", "", "Single Correct")
    assert score_question("", "", 3, 1, "Single Correct") == (0.0, STATUS_UNANSWERED)


def test_jee_adv_sections_marks():
    # Single correct +3 / -1
    assert score_question("a", "a", 3, 1, "Single Correct") == (3.0, STATUS_CORRECT)
    assert score_question("b", "a", 3, 1, "Single Correct") == (-1.0, STATUS_WRONG)
    # Numerical +4 / 0
    assert score_question("7", "7", 4, 0, "Numerical Types/Integer Types", True) == (4.0, STATUS_CORRECT)
    assert score_question("8", "7", 4, 0, "Numerical Types/Integer Types", True) == (0.0, STATUS_WRONG)


# ---------------------------------------------------------------------------
# JEE Advanced multiple-correct partial marking (+4/+3/+2/+1, 0, -2)
# ---------------------------------------------------------------------------
def _multi(user, correct):
    return score_question(user, correct, 4, 2, MULTI, scoring=SCORING_JEE_ADV_MULTI)


def test_multi_full_marks():
    assert _multi("a, b, c, d", "a, b, c, d") == (4.0, STATUS_CORRECT)
    assert _multi("c,a", "a, c") == (4.0, STATUS_CORRECT)


def test_multi_partial_official_cases():
    # all four correct, three chosen -> +3
    assert _multi("a, b, c", "a, b, c, d") == (3.0, STATUS_PARTIAL)
    # three or more correct, two chosen (both correct) -> +2
    assert _multi("a, b", "a, b, c") == (2.0, STATUS_PARTIAL)
    assert _multi("b, d", "a, b, c, d") == (2.0, STATUS_PARTIAL)
    # two or more correct, one chosen (correct) -> +1
    assert _multi("a", "a, c") == (1.0, STATUS_PARTIAL)
    assert _multi("c", "a, b, c") == (1.0, STATUS_PARTIAL)


def test_multi_wrong_and_unanswered():
    assert _multi("a, d", "a, c") == (-2.0, STATUS_WRONG)   # any wrong option
    assert _multi("d", "a, c") == (-2.0, STATUS_WRONG)
    assert _multi("", "a, c") == (0.0, STATUS_UNANSWERED)
    assert _multi(None, "a, c") == (0.0, STATUS_UNANSWERED)


def test_multi_without_scheme_is_all_or_nothing():
    assert score_question("a", "a, c", 4, 2, MULTI) == (-2.0, STATUS_WRONG)
    assert score_question("c, a", "a, c", 4, 2, MULTI) == (4.0, STATUS_CORRECT)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
