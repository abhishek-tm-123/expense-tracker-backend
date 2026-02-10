from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(
    DATABASE_URL, 
    echo=True, 
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