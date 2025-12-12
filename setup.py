"""
Скрипт для настройки проекта D&D Template Forge
"""

import os
import sys
import shutil
from pathlib import Path


def create_directory_structure():
    """Создает структуру директорий проекта"""
    directories = [
        "app/static/css",
        "app/static/js",
        "app/static/images",
        "app/static/avatars",
        "app/static/fonts",
        "app/templates",
        "app/routes",
        "app/utils",
        "logs",
        "uploads"
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Создана директория: {directory}")


def create_default_files():
    """Создает дефолтные файлы"""
    # Создаем дефолтные изображения
    images_dir = Path("app/static/images")

    # Создаем placeholder изображения
    placeholder_images = {
        "logo.png": "Логотип",
        "favicon.ico": "Favicon",
        "hero-bg.jpg": "Фон героя",
        "default-avatar.png": "Аватар по умолчанию"
    }

    for filename, description in placeholder_images.items():
        filepath = images_dir / filename
        if not filepath.exists():
            # Создаем простой placeholder
            from PIL import Image, ImageDraw, ImageFont
            img = Image.new('RGB', (200, 200), color='#1a1a2e')
            d = ImageDraw.Draw(img)

            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()

            d.text((100, 100), description, fill='white', anchor='mm', font=font)
            img.save(filepath)
            print(f"✅ Создано изображение: {filename}")


def create_env_file():
    """Создает .env файл если его нет"""
    env_file = Path(".env")
    if not env_file.exists():
        env_content = """# Настройки Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# Настройки приложения
SECRET_KEY=your-secret-key-change-in-production
ADMIN_CODE=dnd-master-secret-2024
RENDER=false

# Настройки разработки
DEBUG=true
PORT=8000
"""
        env_file.write_text(env_content, encoding='utf-8')
        print("✅ Создан файл .env")
        print("⚠️  Не забудьте изменить SECRET_KEY и ADMIN_CODE!")


def install_requirements():
    """Устанавливает зависимости"""
    print("\n📦 Установка зависимостей...")
    os.system("pip install -r requirements.txt")


def check_redis():
    """Проверяет подключение к Redis"""
    print("\n🔍 Проверка Redis...")
    try:
        import redis
        client = redis.Redis(host='localhost', port=6379)
        client.ping()
        print("✅ Redis подключен")
    except:
        print("⚠️  Redis не подключен. Установите и запустите Redis.")
        print("   Для Windows: https://github.com/microsoftarchive/redis/releases")
        print("   Для macOS: brew install redis && brew services start redis")
        print("   Для Linux: sudo apt-get install redis-server")


def main():
    print("🚀 Настройка D&D Template Forge")
    print("=" * 40)

    create_directory_structure()
    create_default_files()
    create_env_file()

    print("\n📋 Следующие шаги:")
    print("1. Установите зависимости: pip install -r requirements.txt")
    print("2. Запустите Redis сервер")
    print("3. Создайте файл .env с вашими настройками")
    print("4. Запустите приложение: python app/main.py")
    print("\n✨ Настройка завершена!")


if __name__ == "__main__":
    main()
