"""Run with pytest, or:  python -m tests.test_rank_range"""
from app.utils.rank_prediction import calculate_rank_range


def test_range_clamped_to_candidates():
    lower, upper = calculate_rank_range(1_530_000, total_candidates=1_530_000)
    assert upper == 1_530_000 and lower == 1_377_000


def test_range_unclamped_when_inside():
    assert calculate_rank_range(10_000, total_candidates=1_530_000) == (9_000, 11_000)


def test_range_without_total_unchanged():
    assert calculate_rank_range(10_000) == (9_000, 11_000)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")
