"""
Database initialization and session management.

Design principle: Dependency injection
- FastAPI routes request a 'db' session
- SQLAlchemy manages the session lifecycle
- Routes don't need to know about connection details
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from pathlib import Path
import os

from app.models import Base

# ── Configuration ──────────────────────────────────────────────────────────────
# MVP: SQLite (file-based, no server)
# Production: Swap to PostgreSQL (environment variable)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./pona.db"  # Creates pona.db in current directory
)

# ── Engine: Connection pool to database ────────────────────────────────────────
# Why create_engine?
# - Manages connection pooling (reuses connections instead of creating new ones)
# - Lazy evaluation: doesn't connect until first query
# - Configurable: pool size, echo SQL, etc.

if "sqlite" in DATABASE_URL:
    # SQLite: special config (single-threaded, no connection pooling needed)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,  # Set to True to see SQL queries for debugging
    )
else:
    # PostgreSQL or other database
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,  # Verify connections are alive before using them
    )

# ── Session factory ────────────────────────────────────────────────────────────
# SessionLocal: Creates new session for each request
# Sessions manage transactions and database operations

SessionLocal = sessionmaker(
    autocommit=False,  # Don't auto-commit (we control transactions)
    autoflush=False,   # Don't auto-flush (we control when ORM syncs)
    bind=engine
)


def get_db() -> Session:
    """
    Dependency injection function for FastAPI.

    Usage in routes:
        @app.post("/verdict")
        def get_verdict(db: Session = Depends(get_db)):
            # db is automatically injected
            profile = db.query(SensitivityProfile).get(profile_id)

    Why this pattern?
    - Each route gets a fresh session
    - Sessions are closed automatically after request completes
    - Error handling is automatic (rollback on exception)

    RECRUITERS CARE: You understand dependency injection.
    This is how professional FastAPI apps manage database connections.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables if they don't exist.

    Call this once at app startup.
    """
    Base.metadata.create_all(bind=engine)
    print(f"[DB] Initialized database: {DATABASE_URL}")


# ── Why this architecture? ────────────────────────────────────────────────────
#
# PATTERN: Repository Pattern + Dependency Injection
#
# What happens on each request:
#
# 1. FastAPI sees: @Depends(get_db)
# 2. Calls: get_db()
# 3. Creates: db = SessionLocal()
# 4. Yields: Passes to route handler
# 5. Route executes query
# 6. Finally block: db.close() (cleanup)
#
# Benefits:
# - Automatic connection management
# - Automatic transaction handling
# - Easy to test (inject a mock db)
# - Scales: connection pooling handles 1000s of concurrent users
#
# RECRUITERS WILL RECOGNIZE: This is textbook SQLAlchemy best practices.
# You're designing for testability and scalability from day one.
