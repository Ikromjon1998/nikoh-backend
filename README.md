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

### 5. Run Server

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

### 6. Run Tests

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

## Project Structure

```
nikoh-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings and configuration
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   │   └── user.py
│   ├── schemas/             # Pydantic schemas
│   │   └── user.py
│   ├── api/                 # API routes
│   │   └── v1/
│   │       ├── router.py
│   │       └── endpoints/
│   │           └── auth.py
│   ├── core/                # Core utilities
│   │   └── security.py
│   └── services/            # Business logic
│       └── user_service.py
├── tests/
│   ├── conftest.py
│   └── test_auth.py
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## License

MIT
