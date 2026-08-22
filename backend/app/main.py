from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.db_seed import seed_if_empty
from app.api.router import api_router
from app.core.config import get_settings
from app.core.db import SessionLocal, create_schema
from app.models import Base  # noqa: F401  # register mappers

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await create_schema()
    async with SessionLocal() as session:
        await seed_if_empty(session)
    yield


app = FastAPI(title="Dayflow", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
