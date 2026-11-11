"""
Answer matching and per-question scoring.

NEET / JEE Main questions have no `type` and their test sections have no `scoring`.
For them every function below reduces to the original rule:

    correct  -> +marks      (user_answer is not None and user_answer == answer)
    wrong    -> -negative   (user_answer not None and != "")
    skipped  -> 0

JEE Advanced questions carry a `type` (e.g. "True/False", "Multiple Correct"),
which enables tolerant matching, and JEE Advanced "Multiple Correct" sections can
set scoring="jee_adv_multi" for the official partial-marking scheme.
"""

from typing import Optional, Tuple

TYPE_TRUE_FALSE = "True/False"
TYPE_MULTIPLE_CORRECT = "Multiple Correct"
TYPE_NUMERICAL = "Numerical Types/Integer Types"

SCORING_STANDARD = "standard"
SCORING_JEE_ADV_MULTI = "jee_adv_multi"

STATUS_CORRECT = "correct"
STATUS_PARTIAL = "partial"
STATUS_WRONG = "wrong"
STATUS_UNANSWERED = "unanswered"


def _is_blank(value: Optional[str]) -> bool:
    return value is None or str(value).strip() == ""


def _option_set(value: Optional[str]) -> frozenset:
    """'a, c' / 'c,a' / 'A C' -> frozenset({'a', 'c'})."""
    if value is None:
        return frozenset()
    cleaned = str(value).lower().replace(",", " ").replace(";", " ")
    return frozenset(part for part in cleaned.split() if part)


def _as_number(value: Optional[str]) -> Optional[float]:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def answers_match(user_answer: Optional[str], correct_answer: Optional[str],
                  question_type: Optional[str] = None,
                  has_integer_answer: Optional[bool] = False) -> bool:
    """True when the user's answer is fully correct.

    Without a question_type (NEET / JEE Main) this is exactly the original
    rule: user_answer is not None and user_answer == correct_answer.
    """
    if question_type is None:
        return user_answer is not None and user_answer == correct_answer

    # JEE Advanced: never award marks for a blank answer or a blank key.
    if _is_blank(user_answer) or _is_blank(correct_answer):
        return False

    if question_type == TYPE_TRUE_FALSE:
        return str(user_answer).strip().lower() == str(correct_answer).strip().lower()

    if question_type == TYPE_MULTIPLE_CORRECT:
        return _option_set(user_answer) == _option_set(correct_answer)

    if has_integer_answer or question_type == TYPE_NUMERICAL:
        user_num, correct_num = _as_number(user_answer), _as_number(correct_answer)
        if user_num is not None and correct_num is not None:
            return abs(user_num - correct_num) < 1e-9
        return str(user_answer).strip() == str(correct_answer).strip()

    # Single-letter answers (Single Correct, Match, Assertion, Comprehension...)
    return str(user_answer).strip().lower() == str(correct_answer).strip().lower()


def score_question(user_answer: Optional[str], correct_answer: Optional[str],
                   marks: float, negative: float,
                   question_type: Optional[str] = None,
                   has_integer_answer: Optional[bool] = False,
                   scoring: Optional[str] = None) -> Tuple[float, str]:
    """Return (marks_awarded, status) for one question.

    status is one of: correct, partial, wrong, unanswered.
    """
    if (scoring == SCORING_JEE_ADV_MULTI and question_type == TYPE_MULTIPLE_CORRECT):
        return _score_jee_adv_multi(user_answer, correct_answer, marks, negative)

    if answers_match(user_answer, correct_answer, question_type, has_integer_answer):
        return float(marks), STATUS_CORRECT
    if user_answer is not None and user_answer != "":
        return -float(negative), STATUS_WRONG
    return 0.0, STATUS_UNANSWERED


def _score_jee_adv_multi(user_answer: Optional[str], correct_answer: Optional[str],
                         marks: float, negative: float) -> Tuple[float, str]:
    """Official JEE Advanced multiple-correct scheme (marks=4, negative=2):

    +4  all correct options chosen and no wrong option
    +3  all four options correct, exactly three chosen (all correct)
    +2  three or more options correct, exactly two chosen (both correct)
    +1  two or more options correct, exactly one chosen (correct)
     0  not attempted
    -2  any other combination (i.e. any wrong option chosen)

    The partial cases are equivalent to: if the chosen options are a proper,
    non-empty subset of the correct options, award one mark per chosen option.
    """
    chosen = _option_set(user_answer)
    correct = _option_set(correct_answer)
    if not chosen:
        return 0.0, STATUS_UNANSWERED
    if not correct:
        return -float(negative), STATUS_WRONG
    if chosen == correct:
        return float(marks), STATUS_CORRECT
    if chosen < correct:
        return float(min(len(chosen), marks - 1)), STATUS_PARTIAL
    return -float(negative), STATUS_WRONG
