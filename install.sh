#!/bin/bash
# Автоматический скрипт установки бота на VPS/VDS

set -e

echo "╔════════════════════════════════════════╗"
echo "║   🤖 Установка Telegram Bot Polya     ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Проверка прав root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Пожалуйста, запустите скрипт с правами root (sudo)"
    exit 1
fi

BOT_DIR="/opt/bot"

echo "📍 Директория бота: $BOT_DIR"
cd "$BOT_DIR"

# Проверка обязательных файлов
echo ""
echo "🔍 Проверка обязательных файлов..."

required_files=("bot_polya.py" "requirements.txt" ".env")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "❌ Ошибка: Файл $file не найден!"
        echo "   Загрузите все файлы в $BOT_DIR"
        exit 1
    fi
    echo "✅ $file"
done

# Обновление системы
echo ""
echo "📦 Обновление системы..."
apt update -qq
apt upgrade -y -qq

# Установка Python и зависимостей
echo ""
echo "🐍 Установка Python и необходимых пакетов..."
apt install -y python3 python3-pip python3-venv git nano -qq

# Создание виртуального окружения
echo ""
echo "🔧 Создание виртуального окружения..."
if [ -d "venv" ]; then
    echo "⚠️  Виртуальное окружение уже существует, пересоздаём..."
    rm -rf venv
fi
python3 -m venv venv

# Активация и установка зависимостей
echo ""
echo "📥 Установка Python зависимостей..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Проверка .env
echo ""
echo "🔐 Проверка конфигурации..."
if ! grep -q "TELEGRAM_TOKEN" .env 2>/dev/null; then
    echo "⚠️  Предупреждение: TELEGRAM_TOKEN не найден в .env"
    echo "   Отредактируйте файл .env перед запуском"
fi

# Настройка systemd service
echo ""
echo "⚙️  Настройка systemd service..."
if [ -f "bot_polya.service" ]; then
    cp bot_polya.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable bot_polya
    echo "✅ Служба настроена и добавлена в автозагрузку"
else
    echo "⚠️  Файл bot_polya.service не найден, создаём..."
    cat > /etc/systemd/system/bot_polya.service << 'EOF'
[Unit]
Description=Telegram Bot Polya
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/bot
Environment="PATH=/opt/bot/venv/bin"
ExecStart=/opt/bot/venv/bin/python /opt/bot/bot_polya.py
Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=bot_polya

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable bot_polya
    echo "✅ Служба создана и настроена"
fi

# Тестовый запуск (опционально)
echo ""
read -p "🧪 Хотите протестировать запуск бота перед установкой службы? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Запуск тестового режима (Ctrl+C для остановки)..."
    timeout 10s python bot_polya.py || true
fi

# Запуск службы
echo ""
read -p "▶️  Запустить бота сейчас? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    systemctl start bot_polya
    sleep 2
    systemctl status bot_polya --no-pager -l
fi

# Финальная информация
echo ""
echo "╔════════════════════════════════════════╗"
echo "║         ✅ Установка завершена!        ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "📋 Полезные команды:"
echo ""
echo "  systemctl status bot_polya    - Статус бота"
echo "  systemctl start bot_polya     - Запустить"
echo "  systemctl stop bot_polya      - Остановить"
echo "  systemctl restart bot_polya   - Перезапустить"
echo "  journalctl -u bot_polya -f    - Просмотр логов"
echo ""
echo "📝 Для редактирования .env:"
echo "  nano /opt/bot/.env"
echo ""
echo "🎉 Бот готов к работе 24/7!"



