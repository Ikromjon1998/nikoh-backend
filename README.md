# Nikoh Backend

A FastAPI backend for the Nikoh matchmaking platform.

## Tech Stack

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async with asyncpg)
- PostgreSQL
- Pydantic v2
- JWT Authentication

## Setup

### 1. Start PostgreSQL with Docker

```bash
# Start PostgreSQL container
docker run --name nikoh-postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=nikoh_db \
  -p 5432:5432 \
  -d postgres:15

# Create test database
docker exec -it nikoh-postgres psql -U postgres -c "CREATE DATABASE nikoh_test_db;"
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy `.env.example` to `.env` and update values as needed:

```bash
cp .env.example .env
```

### 5. Run Database Migrations

The project uses Alembic for database schema management:

```bash
# Apply all pending migrations
alembic upgrade head
```

### 6. Run Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 7. Run Tests

```bash
pytest -v
```

## API Documentation

Once the server is running, visit:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### Health Check

```bash
curl http://localhost:8000/health
```

### Register User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "phone": "+1234567890",
    "preferred_language": "ru"
  }'
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=securepassword123"
```

### Get Current User

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <your-access-token>"
```

## Database Migrations

The project uses **Alembic** for database migrations. This allows tracking schema changes and applying them consistently across environments.

### Common Migration Commands

```bash
# Apply all pending migrations (run this first for new setups)
alembic upgrade head

# Create new migration after model changes
alembic revision --autogenerate -m "description_of_change"

# Rollback one migration
alembic downgrade -1

# Rollback to specific revision
alembic downgrade <revision_id>

# Show current revision
alembic current

# Show migration history
alembic history
```

### Workflow for Model Changes

1. Modify model in `app/models/`
2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "add_field_to_user"
   ```
3. **Review the generated migration file** (in `alembic/versions/`)
4. Apply migration:
   ```bash
   alembic upgrade head
   ```
5. Commit both model changes and migration file

### For Existing Databases

If you already have tables and want to start using migrations:

```bash
# Mark database as already at current migration state
alembic stamp head
```

### Production Deployment

Always run migrations before starting the application:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0
```

## Project Structure

```
nikoh-backend/
├── alembic/                 # Database migrations
│   ├── env.py              # Migration environment config
│   ├── script.py.mako      # Migration template
│   └── versions/           # Migration files
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings and configuration
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── interest.py
│   │   ├── match.py
│   │   ├── verification.py
│   │   ├── selfie.py
│   │   ├── payment.py
│   │   └── search_preference.py
│   ├── schemas/             # Pydantic schemas
│   ├── api/                 # API routes
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   ├── core/                # Core utilities
│   │   └── security.py
│   └── services/            # Business logic
├── tests/
│   ├── conftest.py
│   └── test_*.py
├── alembic.ini              # Alembic configuration
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## License

MIT
