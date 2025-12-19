# Education API

FastAPI CRUD application with MongoDB for education management.

## Prerequisites

- Python 3.10+
- MongoDB running locally or a MongoDB connection string

## Setup

1. Create virtual environment and install dependencies:
```bash
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Update `.env` with your MongoDB connection:
```
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=education_db
```

## Running the Server

```bash
source venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

Server runs at http://localhost:8000

## API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Courses
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/courses/` | Create course |
| GET | `/api/courses/` | List courses |
| GET | `/api/courses/{id}` | Get course |
| PUT | `/api/courses/{id}` | Update course |
| DELETE | `/api/courses/{id}` | Delete course |

### Subjects
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/subjects/` | Create subject |
| GET | `/api/subjects/` | List subjects (filter: `?course_id=`) |
| GET | `/api/subjects/{id}` | Get subject |
| PUT | `/api/subjects/{id}` | Update subject |
| DELETE | `/api/subjects/{id}` | Delete subject |

### Chapters
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chapters/` | Create chapter |
| GET | `/api/chapters/` | List chapters (filter: `?subject_id=`) |
| GET | `/api/chapters/{id}` | Get chapter |
| PUT | `/api/chapters/{id}` | Update chapter |
| DELETE | `/api/chapters/{id}` | Delete chapter |

### Topics
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/topics/` | Create topic |
| GET | `/api/topics/` | List topics (filter: `?chapter_id=`) |
| GET | `/api/topics/{id}` | Get topic |
| PUT | `/api/topics/{id}` | Update topic |
| DELETE | `/api/topics/{id}` | Delete topic |

### Questions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/questions/` | Create question |
| GET | `/api/questions/` | List questions (filters: `?topic_id=`, `?level=`, `?is_active=`) |
| GET | `/api/questions/{id}` | Get question |
| PUT | `/api/questions/{id}` | Update question |
| DELETE | `/api/questions/{id}` | Delete question |

## Data Model

```
courses
  └── subjects (course_id)
        └── chapters (subject_id)
              └── topics (chapter_id)
                    └── questions (topic_id)
```

## Migration from Supabase

### Data Folder Structure
Place your Supabase JSON exports in the following structure:
```
data/
├── courses/
│   └── courses.json
├── subjects/
│   └── subjects.json
├── chapters/
│   └── chapters.json
├── topics/
│   └── topics.json
└── questions/
    ├── questions_1.json
    ├── questions_2.json
    └── ... (multiple files supported)
```

### Migration API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/migrate/` | Run migration from JSON files |
| DELETE | `/api/migrate/clear` | Clear all data from all collections |

### How Migration Works
1. New UUIDs are generated for all records in MongoDB
2. Foreign key relationships are automatically remapped
3. Data is inserted in dependency order: courses → subjects → chapters → topics → questions

### Run Migration
```bash
curl -X POST http://localhost:8000/api/migrate/
```
