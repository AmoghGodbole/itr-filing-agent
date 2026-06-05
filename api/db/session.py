import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

load_dotenv()

engine = create_async_engine(
    os.environ["DATABASE_URL"],
    echo=False,       # set True to log all SQL (useful for debugging)
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db():
    """FastAPI dependency — yields a DB session, closes it on exit."""
    async with AsyncSessionLocal() as session:
        yield session
