# Деплой на Fly.io (Бесплатный tier)

## Что включено в бесплатную версию

| Компонент | Статус |
|-----------|--------|
| FastAPI Web Server | ✅ |
| PostgreSQL база данных | ✅ (Fly Postgres) |
| Аутентификация (JWT) | ✅ |
| Управление ТЗ | ✅ |
| Экспорт Excel/Word | ✅ |
| Email уведомления | ✅ (нужен SMTP) |
| Telegram уведомления | ✅ (нужен бот) |

### Что убрано (требует платных сервисов)

- ❌ Автоматическая синхронизация с FIPS/WIPO (Celery)
- ❌ Фоновые задачи (Celery Worker)
- ❌ Автоматические периодические уведомления (Celery Beat)
- ❌ MinIO хранилище (заменено на локальные файлы)

## Требования

1. Аккаунт на [fly.io](https://fly.io) (бесплатная регистрация)
2. Установленный `flyctl` CLI

## Установка flyctl

```bash
# macOS
brew install flyctl

# Linux
curl -L https://fly.io/install.sh | sh

# Windows (PowerShell)
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"
```

## Деплой (10 минут)

### 1. Авторизация

```bash
flyctl auth login
```

### 2. Перейдите в папку проекта

```bash
cd trademark_system
```

### 3. Создайте приложение

```bash
flyctl launch --config deploy/flyio/fly.toml --no-deploy
```

Ответьте на вопросы:
- App name: `trademark-system` (или ваше имя)
- Region: выберите ближайший (например, `ams` - Амстердам)

### 4. Создайте PostgreSQL базу данных

```bash
flyctl postgres create --name trademark-db --region ams --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1
```

Это создаст бесплатный PostgreSQL кластер.

### 5. Подключите БД к приложению

```bash
flyctl postgres attach trademark-db --app trademark-system
```

Это автоматически установит `DATABASE_URL` в секреты приложения.

### 6. Создайте volume для файлов

```bash
flyctl volumes create trademark_data --region ams --size 1
```

### 7. Установите секреты

```bash
# Обязательные
flyctl secrets set SECRET_KEY=$(openssl rand -hex 32)
flyctl secrets set JWT_SECRET_KEY=$(openssl rand -hex 32)

# Опционально - Email уведомления
flyctl secrets set SMTP_USER=your-email@gmail.com
flyctl secrets set SMTP_PASSWORD=your-app-password

# Опционально - Telegram уведомления
flyctl secrets set TELEGRAM_BOT_TOKEN=your-bot-token
flyctl secrets set TELEGRAM_CHAT_IDS=123456789
```

### 8. Деплой!

```bash
flyctl deploy --config deploy/flyio/fly.toml
```

### 9. Готово!

```bash
flyctl open
```

Система доступна по адресу: `https://trademark-system.fly.dev`

**Логин:** admin@example.com
**Пароль:** admin123

⚠️ **Сразу смените пароль!**

## Полезные команды

```bash
# Просмотр логов
flyctl logs

# Статус приложения
flyctl status

# SSH в контейнер
flyctl ssh console

# Перезапуск
flyctl apps restart

# Подключение к PostgreSQL
flyctl postgres connect -a trademark-db

# Масштабирование (если нужно больше ресурсов)
flyctl scale memory 512
```

## Ограничения бесплатного tier

| Ресурс | Лимит |
|--------|-------|
| RAM (App) | 512 MB |
| CPU | Shared |
| PostgreSQL | 1 GB storage |
| Volume | 3 GB |
| Bandwidth | 100 GB/мес |
| Auto-stop | Да (засыпает при неактивности) |

### Про Auto-stop

Fly.io автоматически останавливает машину при неактивности и запускает при первом запросе. Первый запрос после сна может занять 3-5 секунд.

Чтобы отключить (платно):
```bash
flyctl scale count 1 --max-per-region 1
```

## Обновление

```bash
cd trademark_system
git pull
flyctl deploy --config deploy/flyio/fly.toml
```

## Резервное копирование PostgreSQL

```bash
# Подключение и экспорт
flyctl postgres connect -a trademark-db
# В psql: \copy (SELECT * FROM trademark) TO '/tmp/backup.csv' CSV HEADER

# Или через pg_dump
flyctl proxy 5432 -a trademark-db &
pg_dump -h localhost -p 5432 -U postgres trademarks > backup.sql
```

## Стоимость

**Бесплатно** при использовании в рамках Free Allowance:
- 3 shared-cpu VMs
- 3 GB persistent storage
- 1 GB PostgreSQL storage
- 100 GB bandwidth

При превышении: ~$3-7/мес

## Проблемы и решения

### Приложение не запускается

```bash
# Проверить логи
flyctl logs

# Проверить статус
flyctl status
```

### Ошибка подключения к БД

```bash
# Проверить, что DATABASE_URL установлен
flyctl secrets list

# Проверить статус PostgreSQL
flyctl postgres list
```

### Нужно больше памяти

```bash
flyctl scale memory 1024
```
(выйдет из бесплатного tier)
