from fastapi import APIRouter, status

router = APIRouter(tags=["healthcheck"])


@router.get("/", status_code=status.HTTP_200_OK)
async def health() -> dict:
    """
    Service healthcheck
    """
    return {"status": "Notification service is OK"}
