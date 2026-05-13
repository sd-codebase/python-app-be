from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.database import connect_to_mongo, close_mongo_connection
from app.utils.rate_limiter import limiter
from app.routes import (
    courses_router,
    subjects_router,
    chapters_router,
    topics_router,
    questions_router,
    migration_router,
    auth_router,
    user_tests_router,
    set_tests_router,
    admin_users_router,
    admin_predefined_tests_router,
    predefined_tests_router,
    test_attempts_router,
    public_router,
    public_solutions_router,
    exam_configs_router,
    global_notifications_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="Education API",
    description="FastAPI CRUD application for education management with MongoDB",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"data": None, "message": "Too many requests. Please try again later."}
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3050",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for resources
app.mount("/resources-data", StaticFiles(directory="resources-data"), name="resources")

app.include_router(auth_router, prefix="/api")
app.include_router(courses_router, prefix="/api")
app.include_router(subjects_router, prefix="/api")
app.include_router(chapters_router, prefix="/api")
app.include_router(topics_router, prefix="/api")
app.include_router(questions_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(public_solutions_router, prefix="/api")
app.include_router(migration_router, prefix="/api")
app.include_router(set_tests_router, prefix="/api")
app.include_router(admin_users_router, prefix="/api")
# User Generated Tests (private to each user)
app.include_router(user_tests_router, prefix="/api")
# Predefined Tests (admin creates, all users can take)
app.include_router(admin_predefined_tests_router, prefix="/api")
app.include_router(predefined_tests_router, prefix="/api")
# Unified Test Attempts (submit any test, view history)
app.include_router(test_attempts_router, prefix="/api")
# Exam Configurations (admin manages exam data for rank prediction)
app.include_router(exam_configs_router, prefix="/api")
app.include_router(global_notifications_router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Education API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
