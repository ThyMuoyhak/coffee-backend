# database.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, MetaData
from databases import Database

# SQLite database URL
DATABASE_URL = "sqlite:///./coffee_shop.db"

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