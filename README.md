### Проектная работа 10 спринта

## Notification service for online cinema
___
### [Репозиторий проекта](https://github.com/KrisMelikova/notifications_sprint_1)
___

### Архитектура проекта

1. [Описание](architecture/README.md)
2. [Диаграмма](architecture/diagram.png)

### Запуск проекта

```
docker compose up --build
or
docker compose up --build -d
```

### Работа с RabbitMQ

Запустить контейнер локально

```
docker run --rm -p 15672:15672 rabbitmq:3.10.7-management
```

Открыть веб-интерфейс RabbitMQ в браузере
(login - guest, password - guest)
```
http://127.0.0.1:15672/
```

### Настройка регулярных оповещений в Airflow

```
1. Переименуйте .env.example в .env
2. Авторизуйтесь в интерфейсе airflow http://localhost:8080
	Логин: airflow
	пароль: airflow
3. В переменных задайте желаемое сообщение и дату доставки рассылки.
4. Запустите DAG "send news"
```
