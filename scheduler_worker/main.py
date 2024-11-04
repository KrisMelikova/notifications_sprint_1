import asyncio

import src.database.mongo as mongo
from settings import scheduler_settings
from src.database import rabbitmq
from src.database.mongo import get_mongo_db
from src.services.send_notification_to_queue import SendNotificationService
from src.services.check_notification import CheckNotificationService

TIME_TO_SLEEP = 10


async def main() -> None:
    """
    A worker who picks up notifications ready to be sent and puts them in a queue.
    """

    mongo.mongo = mongo.init_mongo(
        host=scheduler_settings.mongo.host, port=scheduler_settings.mongo.port
    )
    mongo_db = get_mongo_db(scheduler_settings.mongo.db_name)
    check_notification = CheckNotificationService(
        mongo_db,
        notification_collection=scheduler_settings.mongo.notification_collection,
    )

    rabbitmq.connection = await rabbitmq.create_connection()
    async with rabbitmq.connection:
        rabbitmq.channel = await rabbitmq.create_channel(rabbitmq.connection)
        await rabbitmq.channel.declare_queue(
            scheduler_settings.rabbitmq_queue_notifications, durable=True
        )
        send_notification = SendNotificationService()

        while True:
            notifications = await check_notification.check_notification()
            await send_notification.send_notification_to_queue(
                notifications, rabbitmq.channel
            )
            await asyncio.sleep(TIME_TO_SLEEP)


if __name__ == "__main__":
    asyncio.run(main())
