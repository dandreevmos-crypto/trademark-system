# Trademark Management System

Система управления товарными знаками с автоматическим мониторингом, уведомлениями и интеграцией с ФИПС и WIPO.

## Быстрый старт (Docker)

### Требования
- Docker и Docker Compose

### Запуск за 3 команды

```bash
# 1. Клонировать репозиторий
git clone https://github.com/dandreevmos-crypto/trademark-system.git
cd trademark-system

# 2. Скопировать конфигурацию
cp .env.example .env

# 3. Запустить
docker-compose up -d
```

**Готово!** Система автоматически:
- Создаст базу данных и все таблицы
- Добавит администратора и базовые территории
- Запустит веб-сервер

### Доступ к системе

| Сервис | URL | Логин |
|--------|-----|-------|
| **Web UI** | http://localhost:8000/static/index.html | admin@example.com / admin123 |
| **API Docs** | http://localhost:8000/docs | - |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |

### Управление

```bash
# Просмотр логов
docker-compose logs -f web

# Остановка
docker-compose down

# Остановка с удалением данных
docker-compose down -v

# Перезапуск
docker-compose restart
```

## Импорт данных из Excel

```bash
# Скопируйте Excel файл в папку проекта, затем:
docker-compose exec web python scripts/import_excel.py /app/yourfile.xlsx
```

## Создание дополнительных пользователей

```bash
docker-compose exec web python scripts/create_admin.py user@example.com password123 "Имя Фамилия"
```

## Структура проекта

```
trademark_system/
├── app/
│   ├── api/v1/           # REST API endpoints
│   ├── models/           # SQLAlchemy модели (БД)
│   ├── schemas/          # Pydantic схемы (валидация)
│   ├── services/         # Бизнес-логика
│   ├── integrations/     # FIPS, WIPO, Email, Telegram
│   ├── tasks/            # Celery фоновые задачи
│   ├── static/           # Web UI (HTML/CSS/JS)
│   └── main.py           # FastAPI приложение
├── scripts/              # Утилиты
├── alembic/              # Миграции БД
├── docker/               # Docker конфигурация
└── docker-compose.yml
```

## Основные функции

### Управление товарными знаками
- Каталог ТЗ с фильтрацией по территориям, классам МКТУ, правообладателям
- Отслеживание статусов регистрации
- Мониторинг сроков действия

### Уведомления
- Автоматические уведомления об истечении срока: за 6, 3 и 1 месяц
- Каналы: Email и Telegram
- Возможность отметить "продление подано" или "решено не продлевать"

### Интеграции
- **ФИПС** — автоматический парсинг данных из реестра Роспатента
- **WIPO** — синхронизация с базой Madrid Monitor
- **MinIO** — хранение документов (S3-совместимое)

### Отчёты
- Экспорт в Excel с фильтрами
- Генерация согласительных писем (consent letters)

## API

### Аутентификация
```
POST /api/v1/auth/login          # Вход
POST /api/v1/auth/refresh        # Обновление токена
GET  /api/v1/auth/me             # Текущий пользователь
```

### Товарные знаки
```
GET  /api/v1/trademarks          # Список с фильтрацией
GET  /api/v1/trademarks/{id}     # Детали
POST /api/v1/trademarks          # Создание
PATCH /api/v1/trademarks/{id}    # Обновление
```

### Регистрации
```
GET  /api/v1/registrations/expiring/list     # Истекающие
POST /api/v1/registrations/{id}/renewal-filed    # Отметить продление
POST /api/v1/registrations/{id}/not-renewing     # Отказ от продления
```

### Отчёты
```
GET  /api/v1/reports/export/excel    # Экспорт всего
POST /api/v1/reports/export/excel    # Экспорт с фильтрами
```

## Конфигурация

Основные переменные окружения (`.env`):

| Переменная | Описание |
|------------|----------|
| `SECRET_KEY` | Секретный ключ приложения |
| `JWT_SECRET_KEY` | Ключ для JWT токенов |
| `DATABASE_URL` | URL подключения к PostgreSQL |
| `REDIS_URL` | URL подключения к Redis |
| `SMTP_*` | Настройки почтового сервера |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота |

## Технологии

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Celery
- **Database:** PostgreSQL 15
- **Cache/Queue:** Redis 7
- **Storage:** MinIO
- **Scraping:** Playwright (для ФИПС)
- **Frontend:** Vanilla JS (без фреймворков)

## Лицензия

MIT

---

Создано с помощью [Claude](https://claude.ai)
