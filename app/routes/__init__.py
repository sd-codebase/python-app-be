from app.routes.courses import router as courses_router
from app.routes.subjects import router as subjects_router
from app.routes.chapters import router as chapters_router
from app.routes.topics import router as topics_router
from app.routes.questions import router as questions_router
from app.routes.migration import router as migration_router
from app.routes.auth import router as auth_router
from app.routes.tests import router as user_tests_router
from app.routes.set_tests import router as set_tests_router
from app.routes.admin_users import router as admin_users_router
from app.routes.admin_predefined_tests import router as admin_predefined_tests_router
from app.routes.predefined_tests import router as predefined_tests_router
from app.routes.test_attempts import router as test_attempts_router
from app.routes.public import router as public_router
from app.routes.exam_configs import router as exam_configs_router

__all__ = [
    "courses_router",
    "subjects_router",
    "chapters_router",
    "topics_router",
    "questions_router",
    "migration_router",
    "auth_router",
    "user_tests_router",
    "set_tests_router",
    "admin_users_router",
    "admin_predefined_tests_router",
    "predefined_tests_router",
    "test_attempts_router",
    "public_router",
    "exam_configs_router",
]
