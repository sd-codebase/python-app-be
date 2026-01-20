from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

client: AsyncIOMotorClient = None
db = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.database_name]

    # Create indexes for unique constraints
    await db.courses.create_index("id", unique=True)
    await db.subjects.create_index("id", unique=True)
    await db.chapters.create_index("id", unique=True)
    await db.chapters.create_index([("order_num", 1), ("subject_id", 1)], unique=True)
    await db.topics.create_index("id", unique=True)
    await db.topics.create_index([("order_num", 1), ("chapter_id", 1)], unique=True)
    await db.questions.create_index("id", unique=True)
    await db.questions.create_index([("question", 1), ("answer", 1)], unique=True)

    # User indexes
    await db.users.create_index("id", unique=True)
    await db.users.create_index("email", unique=True)

    # Token blacklist index with TTL (auto-cleanup after token expiry)
    await db.blacklisted_tokens.create_index("token", unique=True)
    await db.blacklisted_tokens.create_index(
        "blacklisted_at",
        expireAfterSeconds=settings.access_token_expire_minutes * 60
    )

    # Generated tests indexes
    await db.generated_tests.create_index("id", unique=True)
    await db.generated_tests.create_index("user_id")
    # Index for efficient rate limiting queries (temp user restrictions)
    await db.generated_tests.create_index([
        ("user_id", 1),
        ("test_type", 1),
        ("created_at", -1)
    ])

    # TTL index to auto-delete temp users after 24 hours
    await db.users.create_index(
        "created_at",
        expireAfterSeconds=86400,
        partialFilterExpression={"user_type": "temp"}
    )

    # Predefined tests indexes
    await db.predefined_tests.create_index("id", unique=True)
    await db.predefined_tests.create_index("status")

    # Test attempts indexes (unified collection for all test types)
    await db.test_attempts.create_index("id", unique=True)
    await db.test_attempts.create_index("user_id")
    await db.test_attempts.create_index("test_id")
    await db.test_attempts.create_index("test_source")
    await db.test_attempts.create_index([("user_id", 1), ("submitted_at", -1)])


async def close_mongo_connection():
    global client
    if client:
        client.close()


def get_database():
    return db
