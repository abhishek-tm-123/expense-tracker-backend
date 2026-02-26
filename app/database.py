from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set.")

engine = create_async_engine(
    DATABASE_URL, 
    echo=DEBUG_MODE, 
    pool_pre_ping=True,
    connect_args={"ssl": "require"}
)

async def create_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

if __name__ == "__main__":
    import asyncio
    asyncio.run(create_db())
    print("Database tables synchronized successfully.")