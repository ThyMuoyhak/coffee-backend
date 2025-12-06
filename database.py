# database.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, MetaData
from databases import Database
import os

# Use environment variable for database URL
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./coffee_shop.db")

# For Render, we need to handle SQLite file path
if DATABASE_URL.startswith("sqlite"):
    # Ensure we have the right path
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite:///app/")
    
# Create SQLAlchemy engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Create metadata
metadata = MetaData()

# Create declarative base
Base = declarative_base()

# Create async database connection
database = Database(DATABASE_URL)

# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency for async database session
async def get_db():
    async with database.transaction():
        yield database