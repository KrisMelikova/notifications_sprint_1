from uuid import UUID, uuid4

from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(tags=["mock_api"])

class NewEpisodeData(BaseModel):
    series_name: str
    episode_name: str
    url: str

class UserProfile(BaseModel):
    email: str
    fullname: str
    notification_settings: dict[str, bool]
    timezone: str


MOCK_EPISODE_DATA = {
    "series_name": "series name",
    "episode_name": "episode name",
    "url": "episode link",
}


@router.get(
    "/profile/{profile_id}",
    status_code=status.HTTP_200_OK,
    description="User Profile Service Mock",
    tags=["profile"],
)
async def get_user_profile() -> UserProfile:
    return UserProfile(
        email="mail@mail.some",
        fullname="Петров Иван Васильевич",
        notification_settings={"email": True, "websocket": True},
        timezone="Europe/Moscow",
    )


@router.get(
    "/filmwork/{filmwork_id}/episode/{episode_id}",
    status_code=status.HTTP_200_OK,
    description="Content service mock",
    tags=["content"],
)
async def get_new_episode() -> NewEpisodeData:
    return NewEpisodeData.model_validate(MOCK_EPISODE_DATA)


@router.get(
    "/subscribers/filmwork/{filmwork_id}",
    status_code=status.HTTP_200_OK,
    description="UGC mock",
    tags=["ugc"],
)
async def get_subscribed_users() -> list[UUID]:
    return [uuid4(), uuid4()]
