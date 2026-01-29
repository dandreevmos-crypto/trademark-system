# Деплой на Render (Бесплатный tier, без карты)

## Что включено

| Компонент | Статус |
|-----------|--------|
| FastAPI Web Server | ✅ |
| PostgreSQL база данных | ✅ (бесплатно 90 дней) |
| Аутентификация (JWT) | ✅ |
| Управление ТЗ | ✅ |
| Экспорт Excel/Word | ✅ |
| Email уведомления | ✅ (нужен SMTP) |
| Telegram уведомления | ✅ (нужен бот) |

### Ограничения бесплатного tier

- ⚠️ Сервис засыпает через 15 минут неактивности (первый запрос ~30 сек)
- ⚠️ PostgreSQL бесплатно только 90 дней, потом нужно пересоздать
- ❌ Нет Celery/Redis (автосинхронизация отключена)

## Деплой за 5 минут

### Способ 1: Через Blueprint (автоматически)

1. Зайдите на [render.com](https://render.com) и зарегистрируйтесь (через GitHub)

2. Нажмите **New** → **Blueprint**

3. Подключите ваш GitHub репозиторий `trademark-system`

4. Render автоматически найдёт `render.yaml` и создаст:
   - Web Service (FastAPI)
   - PostgreSQL Database

5. Нажмите **Apply** — деплой запустится автоматически!

### Способ 2: Вручную

#### 1. Создайте PostgreSQL

1. Зайдите на [render.com](https://render.com)
2. **New** → **PostgreSQL**
3. Настройки:
   - Name: `trademark-db`
   - Region: `Frankfurt (EU Central)`
   - Plan: `Free`
4. Нажмите **Create Database**
5. Скопируйте **Internal Database URL** (понадобится далее)

#### 2. Создайте Web Service

1. **New** → **Web Service**
2. Подключите GitHub репозиторий
3. Настройки:
   - Name: `trademark-system`
   - Region: `Frankfurt (EU Central)`
   - Runtime: `Docker`
   - Dockerfile Path: `./deploy/render/Dockerfile`
   - Plan: `Free`

4. Environment Variables:
   ```
   DATABASE_URL = <Internal Database URL из шага 1>
   SECRET_KEY = <сгенерируйте: openssl rand -hex 32>
   JWT_SECRET_KEY = <сгенерируйте: openssl rand -hex 32>
   CORS_ORIGINS = *
   ```

5. Нажмите **Create Web Service**

### 3. Готово!

Через 5-10 минут система будет доступна:

```
https://trademark-system.onrender.com
```

**Логин:** admin@example.com
**Пароль:** admin123

⚠️ **Сразу смените пароль!**

## Важно знать

### Сервис засыпает

Бесплатные сервисы на Render засыпают через 15 минут неактивности. При первом запросе после сна:
- Ожидание ~30 секунд
- Это нормально для бесплатного tier

### PostgreSQL 90 дней

Бесплатная PostgreSQL база удаляется через 90 дней. Варианты:
1. Пересоздать базу (данные потеряются)
2. Перейти на платный план ($7/мес)
3. Экспортировать данные перед удалением

### Как экспортировать данные

```bash
# Получите External Database URL из настроек БД на Render
pg_dump "postgres://..." > backup.sql
```

## Добавление уведомлений

### Email (Gmail)

В настройках Web Service добавьте:
```
SMTP_USER = your-email@gmail.com
SMTP_PASSWORD = your-app-password
```

[Как создать App Password для Gmail](https://support.google.com/accounts/answer/185833)

### Telegram

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Добавьте переменные:
```
TELEGRAM_BOT_TOKEN = 123456:ABC-DEF...
TELEGRAM_CHAT_IDS = 123456789
```

## Обновление

При push в GitHub — Render автоматически пересоберёт и задеплоит.

Или вручную: **Manual Deploy** → **Deploy latest commit**

## Мониторинг

- Логи: Dashboard → Web Service → Logs
- Метрики: Dashboard → Web Service → Metrics

## Стоимость

| Компонент | Free | Paid |
|-----------|------|------|
| Web Service | ✅ (спит) | $7/мес (не спит) |
| PostgreSQL | 90 дней | $7/мес |

**Итого бесплатно:** 90 дней полностью, потом только Web Service
