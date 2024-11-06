from datetime import datetime, timezone
from typing import Any, Mapping

from motor.motor_asyncio import AsyncIOMotorCursor, AsyncIOMotorDatabase


class CheckNotificationService:
    def __init__(
        self,
        mongo_db: AsyncIOMotorDatabase,
        notification_collection: str,
    ) -> None:
        self.mongo = mongo_db
        self.notification_collection = notification_collection

    async def check_notification(self) -> AsyncIOMotorCursor[Mapping[str, Any] | Any]:
        """A function that collects notifications that are time to be sent to the queue
        (with the status unsent and send_date less than the current time, or None)."""

        return self.mongo[self.notification_collection].find(
            {
                "$and": [
                    {
                        "$or": [
                            {"send_date": {"$lte": datetime.now(timezone.utc)}},
                            {"send_date": None},
                        ]
                    },
                    {"status": "unsent"},
                ]
            }
        )
