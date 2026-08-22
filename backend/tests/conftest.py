import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.db_seed import seed_if_empty
from app.core.db import SessionLocal, engine
from app.main import app
from app.models import Base


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_if_empty(session)
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
