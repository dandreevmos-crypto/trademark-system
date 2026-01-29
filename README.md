# Trademark Management System

Система управления товарными знаками с автоматическим мониторингом, уведомлениями и интеграцией с ФИПС и WIPO.

## Быстрый старт

### 1. Запуск с Docker Compose (рекомендуется)

```bash
# Скопировать конфигурацию
cp .env.example .env

# Отредактировать .env (особенно SECRET_KEY и JWT_SECRET_KEY)
nano .env

# Запустить все сервисы
docker-compose up -d

# Проверить статус
docker-compose ps

# Просмотреть логи
docker-compose logs -f web
```

После запуска:
- API доступен на http://localhost:8000
- Документация API: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin)

### 2. Создание администратора

```bash
# Через Docker
docker-compose exec web python scripts/create_admin.py admin@example.com yourpassword "Имя Администратора"

# Или локально
python scripts/create_admin.py admin@example.com yourpassword
```

### 3. Импорт данных из Excel

```bash
# Через Docker
docker-compose exec web python scripts/import_excel.py /path/to/excel.xlsx

# Или локально
python scripts/import_excel.py "Актуальный реестр товарных знаков.xlsx"
```

## Структура проекта

```
trademark_system/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── models/           # SQLAlchemy модели
│   ├── schemas/          # Pydantic схемы
│   ├── services/         # Бизнес-логика
│   ├── integrations/     # Интеграции (FIPS, WIPO, Email, Telegram)
│   ├── tasks/            # Celery задачи
│   ├── core/             # Аутентификация, безопасность
│   └── main.py           # FastAPI приложение
├── scripts/              # Скрипты импорта/администрирования
├── docker/               # Docker конфигурация
└── docker-compose.yml
```

## API Endpoints

### Аутентификация
- `POST /api/v1/auth/login` - Вход
- `POST /api/v1/auth/refresh` - Обновление токена
- `GET /api/v1/auth/me` - Информация о пользователе

### Товарные знаки
- `GET /api/v1/trademarks` - Список с фильтрацией
- `GET /api/v1/trademarks/{id}` - Детали знака
- `POST /api/v1/trademarks` - Создание (admin)
- `PATCH /api/v1/trademarks/{id}` - Обновление (admin)

### Регистрации
- `GET /api/v1/registrations/expiring/list` - Истекающие регистрации
- `POST /api/v1/registrations/{id}/renewal-filed` - Отметить продление
- `POST /api/v1/registrations/{id}/not-renewing` - Отметить отказ от продления

### Отчёты
- `GET /api/v1/reports/export/excel` - Экспорт в Excel
- `POST /api/v1/reports/export/excel` - Экспорт с фильтрами

## Фильтры экспорта

```json
{
  "rights_holder_ids": ["uuid1", "uuid2"],
  "territory_ids": [1, 2],
  "icgs_classes": [25, 35],
  "product_groups": ["Обувь", "Одежда"],
  "statuses": ["registered"],
  "renewal_statuses": ["active"],
  "expiration_from": "2024-01-01",
  "expiration_to": "2024-12-31",
  "include_expired": false,
  "include_rejected": false
}
```

## Уведомления

Система отправляет уведомления об истечении срока действия:
- За 6 месяцев
- За 3 месяца
- За 1 месяц

Каналы: Email и Telegram

Чтобы остановить уведомления:
1. Отметить "Продление подано" (`POST /registrations/{id}/renewal-filed`)
2. Отметить "Решено не продлевать" (`POST /registrations/{id}/not-renewing`)

## Настройка Telegram бота

1. Создать бота через @BotFather
2. Получить токен
3. Добавить в `.env`:
   ```
   TELEGRAM_BOT_TOKEN=your-bot-token
   ```
4. Пользователь должен написать `/start` боту
5. Привязать Telegram ID в профиле пользователя

## Разработка

### Локальная установка

```bash
# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Установить Playwright браузеры
playwright install chromium

# Запустить PostgreSQL и Redis (docker)
docker-compose up -d db redis

# Запустить приложение
uvicorn app.main:app --reload

# Запустить Celery worker
celery -A app.tasks.celery_app worker -l info

# Запустить Celery beat
celery -A app.tasks.celery_app beat -l info
```

## Технологии

- **Backend:** FastAPI, SQLAlchemy, Celery
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis 7
- **Storage:** MinIO (S3-compatible)
- **Scraping:** Playwright
# trademark-system
