## Notification service

### Запуск сервиса для локальной разработки
```
1. cd notification_service
2. cp .env.example .env
3. python3.11 -m venv venv
4. source venv/bin/activate
5. pip3 install poetry
6. python -m poetry install
7. uvicorn src.main:app --reload --host 0.0.0.0 --port 8005
```