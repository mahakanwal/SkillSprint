"""
database/connection.py
Handles PostgreSQL connection using SQLAlchemy.
"""


import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from dotenv import load_dotenv


load_dotenv()



DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@localhost:5432/skillsprint_db"
)



# SQLite (used by the automated tests) needs cross-thread access for the
# FastAPI test client; PostgreSQL ignores this branch.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)



SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)



Base = declarative_base()




def get_db():

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()




def init_db():

    # Import models so every table is registered on Base before create_all.
    import database.models  # noqa: F401
    from database.migrations import upgrade_schema

    Base.metadata.create_all(
        bind=engine
    )

    # Add any newly introduced columns to tables that already existed.
    added = upgrade_schema(engine, Base)
    if added:
        print("Schema upgraded, added columns:", ", ".join(added))