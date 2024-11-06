from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from src.api.v1 import mock
from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    version="1.0.0",
    title=settings.project_name,
    description="Mock API",
    docs_url="/api/openapi",
    openapi_url="/api/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    contact={
        "name": "Monty Python",
        "email": "monty@python.com",
    },
)

app.include_router(mock.router, prefix="/api/v1")

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
