#!/bin/bash
# Скрипт для быстрого развёртывания на Yandex Cloud VM
# Запускать на свежей Ubuntu 22.04

set -e

echo "=========================================="
echo "  Установка Trademark System"
echo "=========================================="

# Обновление системы
echo "[1/6] Обновление системы..."
sudo apt-get update
sudo apt-get upgrade -y

# Установка Docker
echo "[2/6] Установка Docker..."
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Клонирование репозитория
echo "[3/6] Клонирование репозитория..."
cd ~
git clone https://github.com/dandreevmos-crypto/trademark-system.git
cd trademark-system

# Настройка .env
echo "[4/6] Настройка конфигурации..."
cp .env.example .env

# Генерация секретных ключей
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

sed -i "s/your-super-secret-key-change-me/$SECRET_KEY/" .env
sed -i "s/your-jwt-secret-key-change-me/$JWT_SECRET/" .env

# Запуск
echo "[5/6] Запуск Docker контейнеров..."
sudo docker compose up -d

# Настройка Nginx (reverse proxy с HTTPS)
echo "[6/6] Установка Nginx..."
sudo apt-get install -y nginx

# Получаем внешний IP
EXTERNAL_IP=$(curl -s ifconfig.me)

# Конфигурация Nginx
sudo tee /etc/nginx/sites-available/trademark > /dev/null <<EOF
server {
    listen 80;
    server_name $EXTERNAL_IP _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/trademark /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
sudo systemctl enable nginx

echo ""
echo "=========================================="
echo "  Установка завершена!"
echo "=========================================="
echo ""
echo "Система доступна по адресу: http://$EXTERNAL_IP"
echo ""
echo "Логин: admin@example.com"
echo "Пароль: admin123"
echo ""
echo "Важно: Смените пароль после первого входа!"
echo ""
