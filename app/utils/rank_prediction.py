"""
Rank Prediction and Percentile Calculation Utility

This module provides rank prediction functionality based on exam configuration
data stored in the database.
"""

from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class PredictionResult:
    """Result of rank prediction calculation."""
    percentile: float
    predicted_rank: int
    rank_range_lower: int
    rank_range_upper: int
    normalized_score: float
    exam_max_score: int
    exam_type: str
    data_year: str

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "percentile": round(self.percentile, 2),
            "predicted_rank": self.predicted_rank,
            "rank_range": {
                "lower": self.rank_range_lower,
                "upper": self.rank_range_upper,
            },
            "normalized_score": round(self.normalized_score, 2),
            "exam_max_score": self.exam_max_score,
            "exam_type": self.exam_type,
            "prediction_data_year": self.data_year,
        }


def normalize_score(test_score: float, test_max_score: float, exam_max_score: int) -> float:
    """
    Normalize a test score to the exam's maximum score scale.

    Example: 20-question test, 4 marks each (max=80), user scores 60
    For NEET (max=720): (60/80) * 720 = 540
    """
    if test_max_score <= 0:
        return 0.0
    return (test_score / test_max_score) * exam_max_score


def calculate_percentile(score: float, score_percentile_data: List[Tuple[int, float]]) -> float:
    """
    Calculate percentile using linear interpolation between score-percentile data points.

    Args:
        score: The normalized score
        score_percentile_data: List of (score, percentile) tuples sorted in descending order

    Returns:
        Interpolated percentile value
    """
    if not score_percentile_data:
        return 0.0

    # Score above max
    if score >= score_percentile_data[0][0]:
        return score_percentile_data[0][1]

    # Score below min
    if score <= score_percentile_data[-1][0]:
        return score_percentile_data[-1][1]

    # Find the two data points to interpolate between
    for i in range(len(score_percentile_data) - 1):
        upper_score, upper_percentile = score_percentile_data[i]
        lower_score, lower_percentile = score_percentile_data[i + 1]

        if lower_score <= score <= upper_score:
            # Linear interpolation
            if upper_score == lower_score:
                return upper_percentile

            ratio = (score - lower_score) / (upper_score - lower_score)
            return lower_percentile + ratio * (upper_percentile - lower_percentile)

    return 0.0


def calculate_rank(percentile: float, total_candidates: int) -> int:
    """
    Calculate predicted rank from percentile.

    Formula: rank = (1 - percentile/100) * total_candidates
    """
    if percentile >= 100:
        return 1
    rank = int((1 - percentile / 100) * total_candidates)
    return max(1, rank)


def calculate_rank_range(predicted_rank: int, margin_percent: float = 10.0) -> Tuple[int, int]:
    """
    Calculate rank range with a margin of error.

    Args:
        predicted_rank: The predicted rank
        margin_percent: Percentage margin (default 10%)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    margin = int(predicted_rank * margin_percent / 100)
    lower = max(1, predicted_rank - margin)
    upper = predicted_rank + margin
    return lower, upper


async def get_exam_config(db, exam_type: str) -> Optional[dict]:
    """
    Fetch exam configuration from the database.

    Args:
        db: Database connection
        exam_type: The exam type (e.g., NEET, JEE_MAIN)

    Returns:
        Exam config document or None if not found
    """
    return await db.exam_configs.find_one({
        "exam_type": exam_type,
        "is_active": True
    })


async def predict_rank(
    db,
    score: float,
    max_score: float,
    exam_type: str
) -> Optional[PredictionResult]:
    """
    Predict rank based on test score and exam configuration from database.

    Args:
        db: Database connection
        score: The test score achieved
        max_score: Maximum possible score for the test
        exam_type: The exam type (e.g., NEET, JEE_MAIN)

    Returns:
        PredictionResult with all calculated values, or None if exam config not found
    """
    # Fetch exam config from database
    config = await get_exam_config(db, exam_type)
    if not config:
        return None

    exam_max_score = config["exam_max_score"]
    total_candidates = config["total_candidates"]
    data_year = config.get("data_year", "2025")

    # Convert score_percentile from list of dicts to list of tuples
    score_percentile_data = [
        (sp["score"], sp["percentile"])
        for sp in config["score_percentile"]
    ]

    # Normalize score to exam scale
    normalized_score = normalize_score(score, max_score, exam_max_score)

    # Calculate percentile
    percentile = calculate_percentile(normalized_score, score_percentile_data)

    # Calculate rank
    predicted_rank = calculate_rank(percentile, total_candidates)

    # Calculate rank range
    rank_lower, rank_upper = calculate_rank_range(predicted_rank)

    return PredictionResult(
        percentile=percentile,
        predicted_rank=predicted_rank,
        rank_range_lower=rank_lower,
        rank_range_upper=rank_upper,
        normalized_score=normalized_score,
        exam_max_score=exam_max_score,
        exam_type=exam_type,
        data_year=data_year,
    )


async def get_exam_type_from_course(
    db,
    test_type: str,
    reference_id: str
) -> Optional[str]:
    """
    Resolve the exam_type from the course in the test's reference hierarchy.

    The course name is used as the exam_type. For example, a course named "NEET"
    will match an exam_config with exam_type "NEET".

    Args:
        db: Database connection
        test_type: The type of test (topic, chapter, subject, course)
        reference_id: The ID of the reference entity

    Returns:
        Exam type (course name) if found, None otherwise
    """
    if not test_type or not reference_id:
        return None

    test_type_lower = test_type.lower()
    course = None

    if test_type_lower == "course":
        course = await db.courses.find_one({"id": reference_id})

    elif test_type_lower == "subject":
        subject = await db.subjects.find_one({"id": reference_id})
        if subject and subject.get("course_id"):
            course = await db.courses.find_one({"id": subject["course_id"]})

    elif test_type_lower == "chapter":
        chapter = await db.chapters.find_one({"id": reference_id})
        if chapter and chapter.get("subject_id"):
            subject = await db.subjects.find_one({"id": chapter["subject_id"]})
            if subject and subject.get("course_id"):
                course = await db.courses.find_one({"id": subject["course_id"]})

    elif test_type_lower == "topic":
        topic = await db.topics.find_one({"id": reference_id})
        if topic and topic.get("chapter_id"):
            chapter = await db.chapters.find_one({"id": topic["chapter_id"]})
            if chapter and chapter.get("subject_id"):
                subject = await db.subjects.find_one({"id": chapter["subject_id"]})
                if subject and subject.get("course_id"):
                    course = await db.courses.find_one({"id": subject["course_id"]})

    if course:
        # Use exam_type field if set, otherwise use course name
        return course.get("exam_type") or course.get("name")

    return None


async def get_rank_prediction(
    db,
    score: float,
    max_score: float,
    exam_type: str
) -> Optional[dict]:
    """
    Convenience function to get rank prediction as a dictionary.

    Args:
        db: Database connection
        score: The test score achieved
        max_score: Maximum possible score for the test
        exam_type: The exam type (e.g., NEET, JEE_MAIN)

    Returns:
        Dictionary with prediction data, or None if exam config not found
    """
    if not exam_type:
        return None

    prediction = await predict_rank(db, score, max_score, exam_type)
    if not prediction:
        return None

    return prediction.to_dict()


async def get_rank_prediction_from_test(
    db,
    score: float,
    max_score: float,
    test_type: str,
    reference_id: str
) -> Optional[dict]:
    """
    Get rank prediction by resolving exam_type from the test's course hierarchy.

    Args:
        db: Database connection
        score: The test score achieved
        max_score: Maximum possible score for the test
        test_type: The type of test (topic, chapter, subject, course)
        reference_id: The ID of the reference entity

    Returns:
        Dictionary with prediction data, or None if not applicable
    """
    exam_type = await get_exam_type_from_course(db, test_type, reference_id)
    if not exam_type:
        return None

    return await get_rank_prediction(db, score, max_score, exam_type)
