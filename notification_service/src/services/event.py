from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta, timezone
from logging import getLogger
from uuid import UUID
from zoneinfo import ZoneInfo


import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.constants import ChannelEnum, EventsEnum
from src.event_worker.rabbitmq import send_message
from src.event_worker.settings import settings
from src.models.etc import NewEpisodeData, UserProfile
from src.models.event import Event, NewEpisodeEventData
from src.models.notification import (
    NotificationDB,
    NotificationEmailData,
    NotificationQueue,
)
from src.services.template import TemplateService

logger = getLogger()


class BaseEventHandler(ABC):
    """
    Notification event handler
    """

    def __init__(
        self,
        mongo_db: AsyncIOMotorDatabase,
        template_service: TemplateService,
        event_collection: str,
        notification_collection: str,
    ) -> None:
        self.ugc_service_client = None
        self.content_service_client = None
        self.profile_service_client = None
        self.mongo = mongo_db
        self.event_collection = event_collection
        self.notification_collection = notification_collection
        self.temlate_service = template_service
        self.profile_service_url = (
            f"http://{settings.profile_service_host}:{settings.profile_service_port}"
        )
        self.content_service_url = (
            f"http://{settings.content_service_host}:{settings.content_service_port}"
        )
        self.ugc_service_url = (
            f"http://{settings.ugc_service_host}:{settings.ugc_service_port}"
        )

    async def setup(self):
        self.profile_service_client = httpx.AsyncClient()
        self.content_service_client = httpx.AsyncClient()
        self.ugc_service_client = httpx.AsyncClient()

    async def cleanup(self):
        await self.profile_service_client.aclose()
        await self.content_service_client.aclose()
        await self.ugc_service_client.aclose()

    async def __aenter__(self):
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.cleanup()
        if exc_type:
            return False

    async def process(self, raw_event: dict) -> None:
        event = Event.model_validate(raw_event)
        event = await self._save_event(event)
        await self.process_event(event)

    @abstractmethod
    async def process_event(self, event: Event) -> None:
        """
        An abstract method for processing a notification event,
        overloaded with specific handlers
        """

    async def _send_notification(self, notification: NotificationDB) -> None:
        """
        Saving the notification in the database and sending it to the instant message queue
        """
        try:
            result = await self.mongo[
                settings.mongo.notification_collection
            ].insert_one(notification.model_dump())
        except Exception:
            logger.exception(f"Error while saving notification to Mongo {notification}")
            raise
        else:
            notification_id = str(result.inserted_id)
            logger.info(f"New notification has been saved in the database {notification}")

        if notification.send_date is None:
            queue_notification = NotificationQueue(
                message=notification.message,
                channel=notification.channel,
                data=notification.data,
                notification_id=notification_id,
            )
            await self._send_notification_to_queue(queue_notification)

    async def _get_user_profile(self, user_id: UUID | str) -> UserProfile:
        """
        Obtaining user information
        """
        url = f"{self.profile_service_url}/api/v1/profile/{user_id}"

        try:
            response = await self.profile_service_client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(f"failed to get user profile {user_id}")
            raise
        data = response.json()

        return UserProfile.model_validate(data)

    async def _get_new_episode_data(
        self, filmwork_id: UUID, episode_id: UUID
    ) -> NewEpisodeData:
        """
        Retrieving episode data
        """

        url = f"{self.profile_service_url}/api/v1/filmwork/{filmwork_id}/episode/{episode_id}"

        try:
            response = await self.profile_service_client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(f"Failed to get episode data {filmwork_id=} {episode_id=}")
            raise
        data = response.json()

        return NewEpisodeData.model_validate(data)

    async def _get_filmwork_subscribers(self, filmwork_id: UUID) -> list[UUID]:
        """
        Getting subscribers for a film/series
        """
        url = f"{self.profile_service_url}/api/v1/subscribers/filmwork/{filmwork_id}"

        try:
            response = await self.profile_service_client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception(f"Failed to get subscribers for {filmwork_id=}")
            raise

        return response.json()

    async def _save_event(self, event: Event) -> Event:
        """
        Saving event to DB
        """
        try:
            result = await self.mongo[self.event_collection].insert_one(
                event.model_dump(exclude={"id"})
            )
        except Exception:
            logger.exception(f"Error while saving event to mongo {event}")
            raise

        event.id = str(result.inserted_id)
        return event

    async def _send_notification_to_queue(
        self, notification: NotificationQueue
    ) -> None:
        """
        Sends notification to queue
        """
        try:
            await send_message(
                notification.model_dump(),
                queue_name=settings.rabbitmq_queue_notifications,
            )
        except Exception:
            logger.exception(
                f"Error while trying to send notification to rabbitmq {notification}"
            )
            raise
        else:
            logger.info(f"Sent new notification to queue {notification}")

    def is_user_nighttime(
        self, user_timezone: str, send_date: datetime | None
    ) -> tuple[datetime, bool]:
        """
        Checks whether the sending time falls during the night for the user
        """
        night_start = time(settings.nighttime_start_hour, 0)
        night_end = time(settings.nighttime_end_hour, 0)

        if send_date is None:
            user_send_date = datetime.now(tz=ZoneInfo(user_timezone))
        else:
            user_send_date = send_date.astimezone(tz=ZoneInfo(user_timezone))
        user_send_time = user_send_date.time()

        nighttime_flag = (night_start <= user_send_time) or (user_send_time < night_end)
        return user_send_date, nighttime_flag

    def calculate_send_datetime(
        self, user_timezone: str, send_date: datetime | None
    ) -> datetime | None:
        """
        Calculates the sending time based on the user time zone
        """
        user_send_date, nighttime_flag = self.is_user_nighttime(
            user_timezone, send_date
        )
        if nighttime_flag:
            if user_send_date.time() < time(settings.nighttime_start_hour, 0):
                next_notification_time = user_send_date.replace(
                    hour=7, minute=0, second=0, microsecond=0
                )
            else:
                next_day = user_send_date + timedelta(days=1)
                next_notification_time = next_day.replace(
                    hour=7, minute=0, second=0, microsecond=0
                )
            next_notification_time.astimezone(tz=timezone.utc)
            return next_notification_time

        return send_date


EVENT_HANDLER_REGISTRY: dict[str, type[BaseEventHandler]] = {}


def register_event_handler(event_type: EventsEnum):
    """
    Decorator for adding event handlers to the registry
    """

    def decorator(event_class):
        EVENT_HANDLER_REGISTRY[event_type] = event_class
        return event_class

    return decorator


@register_event_handler(EventsEnum.NEW_USER)
class NewUserEvent(BaseEventHandler):
    """
    New user registration confirmation
    """

    urgent: bool = True

    async def process_event(self, event: Event) -> None:
        user_id = event.data["user_id"]
        user_profile = await self._get_user_profile(user_id)
        context = {
            "fullname": user_profile.fullname,
            "url": event.data["url"],
        }
        user_email = user_profile.email

        notification_channel = ChannelEnum.EMAIL
        template_str = self.temlate_service.get_template(
            event.type, notification_channel
        )
        message = self.temlate_service.render_template(template_str, context)
        logger.debug(message)

        send_data = NotificationEmailData(
            email=user_email, subject="Подтверждение регистрации в онлайн-кинотеатре"
        )

        db_notification = NotificationDB(
            message=message,
            channel=notification_channel,
            send_date=event.send_date,
            data=send_data.model_dump(),
            updated_at=datetime.now(tz=timezone.utc),
        )
        await self._send_notification(db_notification)


@register_event_handler(EventsEnum.SERIES)
class NewEpisodeEvent(BaseEventHandler):
    """
    New episode event handler
    """

    urgent: bool = True

    async def process_event(self, event: Event) -> None:
        event_data = NewEpisodeEventData.model_validate(event.data)
        subscribed_users = await self._get_filmwork_subscribers(event_data.filmwork_id)
        filmwork_data = await self._get_new_episode_data(
            event_data.filmwork_id, event_data.episode_id
        )
        for user_id in subscribed_users:
            user_profile = await self._get_user_profile(user_id)
            user_send_date = self.calculate_send_datetime(
                user_profile.timezone, event.send_date
            )

            notification_channel = ChannelEnum.EMAIL
            if user_profile.notification_settings[notification_channel]:
                user_email = user_profile.email
                email_context = {
                    "fullname": user_profile.fullname,
                    "series_name": filmwork_data.series_name,
                    "episode_name": filmwork_data.episode_name,
                    "url": filmwork_data.url,
                }
                template_str = self.temlate_service.get_template(
                    event.type, notification_channel
                )
                message = self.temlate_service.render_template(
                    template_str, email_context
                )
                send_data = NotificationEmailData(
                    email=user_email,
                    subject=f"Online Cinema: {filmwork_data.series_name} вышла новая серия!",
                )
                db_notification = NotificationDB(
                    message=message,
                    channel=notification_channel,
                    send_date=user_send_date,
                    data=send_data.model_dump(),
                    updated_at=datetime.now(tz=timezone.utc),
                )
                await self._send_notification(db_notification)

            notification_channel = ChannelEnum.WEBSOCKET
            if user_profile.notification_settings[notification_channel]:
                context = {
                    "fullname": user_profile.fullname,
                    "series_name": filmwork_data.series_name,
                    "episode_name": filmwork_data.episode_name,
                    "url": filmwork_data.url,
                }
                template_str = self.temlate_service.get_template(
                    event.type, notification_channel
                )
                message = self.temlate_service.render_template(template_str, context)
                db_notification = NotificationDB(
                    message=message,
                    channel=notification_channel,
                    send_date=user_send_date,
                    data={},
                    updated_at=datetime.now(tz=timezone.utc),
                )
                await self._send_notification(db_notification)
