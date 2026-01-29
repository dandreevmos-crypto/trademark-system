# Развёртывание в Яндекс Облаке

## Шаг 1: Создание виртуальной машины

1. Откройте [console.cloud.yandex.ru](https://console.cloud.yandex.ru)

2. Перейдите в **Compute Cloud** → **Создать ВМ**

3. Настройки ВМ:
   - **Имя:** `trademark-system`
   - **Зона:** любая (например, `ru-central1-a`)
   - **ОС:** Ubuntu 22.04 LTS
   - **Платформа:** Intel Ice Lake
   - **vCPU:** 2 (минимум)
   - **RAM:** 4 ГБ (минимум)
   - **Диск:** 20 ГБ SSD
   - **Публичный IP:** Автоматически

4. **SSH-ключ:** Добавьте свой публичный SSH ключ
   - Если нет ключа, создайте: `ssh-keygen -t ed25519`
   - Скопируйте содержимое `~/.ssh/id_ed25519.pub`

5. Нажмите **Создать ВМ**

## Шаг 2: Подключение и установка

После создания ВМ (2-3 минуты), скопируйте её внешний IP и выполните:

```bash
# Подключение к серверу
ssh yc-user@<ВНЕШНИЙ_IP>

# Скачивание и запуск скрипта установки
curl -sSL https://raw.githubusercontent.com/dandreevmos-crypto/trademark-system/main/deploy/yandex-cloud/setup.sh | bash
```

## Шаг 3: Готово!

После завершения скрипта (5-10 минут) система будет доступна:

```
http://<ВНЕШНИЙ_IP>
```

**Логин:** admin@example.com
**Пароль:** admin123

## Настройка домена (опционально)

Если хотите использовать свой домен вместо IP:

1. Добавьте A-запись в DNS вашего домена:
   ```
   trademark.yourdomain.com → <ВНЕШНИЙ_IP>
   ```

2. Подключитесь к серверу и настройте HTTPS:
   ```bash
   ssh yc-user@<ВНЕШНИЙ_IP>

   # Установка Certbot
   sudo apt install -y certbot python3-certbot-nginx

   # Получение SSL сертификата
   sudo certbot --nginx -d trademark.yourdomain.com
   ```

3. Теперь система доступна по: `https://trademark.yourdomain.com`

## Стоимость

Примерная стоимость в Яндекс Облаке:
- **ВМ (2 vCPU, 4 GB RAM):** ~2000 ₽/мес
- **Диск 20 ГБ SSD:** ~100 ₽/мес
- **Трафик:** ~50 ₽/мес

**Итого:** ~2150 ₽/мес

## Управление

```bash
# Подключение к серверу
ssh yc-user@<ВНЕШНИЙ_IP>

# Просмотр логов
cd ~/trademark-system
sudo docker compose logs -f web

# Перезапуск
sudo docker compose restart

# Остановка
sudo docker compose down

# Обновление до новой версии
cd ~/trademark-system
git pull
sudo docker compose up -d --build
```
