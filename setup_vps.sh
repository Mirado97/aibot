#!/bin/bash
# Установка бота на Ubuntu 24 LTS
# Запускать от root или через sudo
# Использование: bash setup_vps.sh

set -e

echo "=== Обновление системы ==="
apt-get update && apt-get upgrade -y

echo "=== Установка Docker ==="
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== Клонирование репозитория ==="
cd /opt
git clone https://github.com/Mirado97/aibot.git
cd aibot

echo "=== Создание .env ==="
cp .env.example .env
echo ""
echo "!!! ВАЖНО: отредактируй /opt/aibot/.env — вставь API ключи OKX !!!"
echo "    nano /opt/aibot/.env"
echo ""

echo "=== Готово ==="
echo "Следующие шаги:"
echo "  1. nano /opt/aibot/.env          — вставить API ключи"
echo "  2. cd /opt/aibot"
echo "  3. docker compose up --build     — первый запуск (скачает данные ~4 мин)"
echo "  4. docker compose up -d          — фоновый запуск"
echo "  5. docker compose logs -f        — смотреть логи"
