from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from src.api.v1 import healthcheck, notification
from src.core.config import settings
from src.db import rabbitmq


@asynccontextmanager
async def lifespan(app: FastAPI):
    rabbitmq.connection = await rabbitmq.create_connection_rabbitmq()
    rabbitmq.channel = await rabbitmq.create_channel_rabbitmq(rabbitmq.connection)

    await rabbitmq.init_queues(rabbitmq.channel)
    yield
    await rabbitmq.connection.close()


app = FastAPI(
    version="1.0.0",
    title=settings.project_name,
    description="Notification service for online cinema",
    docs_url="/api/docs",
    openapi_url="/api/docs.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
    contact={
        "name": "Monty Python",
        "email": "monty@python.com",
    },
)

app.include_router(healthcheck.router, prefix="/api/v1/healthcheck")
app.include_router(notification.router, prefix="/api/v1/notification")

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)
