# 🎲 DND Issue Templates for GitHub

![GitHub Issues](https://img.shields.io/badge/GitHub-Issues-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.0-green)
![Python](https://img.shields.io/badge/Python-3.9+-yellow)
![Redis](https://img.shields.io/badge/Redis-Cached-red)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

Умный инструмент для создания структурированных GitHub Issues с использованием шаблонов для DND-проектов и геймдева.

[English](#english) | [Русский](#русский)

---

## 📸 Скриншоты

| Главное меню | Создание шаблона |
|-----------------------------------|----------------------------|
| ![Управление репозиториями](docs/screens/v0.0.2/2025-12-13_00-01-54.png) | ![Создание Issue](docs/screens/v0.0.2/2025-12-13_00-01-03.png) |

| Коллекции | Настройки аккунта |
|-----------------------|---------------------|
| ![Предпросмотр](docs/screens/v0.0.2/2025-12-13_00-01-29.png) | ![Активность](docs/screens/v0.0.2/2025-12-13_00-14-49.png) |
| ![Предпросмотр](docs/screens/v0.0.2/2025-12-13_00-12-19.png) | |

---

## ✨ Особенности

### 🎯 Для DND проектов
- **Специализированные шаблоны** для кампаний, персонажей, локаций
- **Автоматическое форматирование** для DND-контента
- **Поддержка Markdown** с DND-стилями

### 🔧 Технические возможности
- **Подключение нескольких репозиториев** GitHub
- **Безопасное хранение токенов** с шифрованием
- **Предпросмотр в реальном времени**
- **Автосохранение черновиков**
- **История активности**

### 🚀 Быстрый старт
- **Интуитивный интерфейс** - работайте за минуты
- **Готовые шаблоны** - экономьте время
- **Автодеплой** на Render.com

---

## 🚀 Быстрый старт

### Локальная установка

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/dnd-issues-creator.git
cd dnd-issues-creator

# Установка зависимостей
pip install -r requirements.txt

# Запуск Redis (Docker)
docker run -d -p 6379:6379 redis:alpine

# Запуск приложения
uvicorn backend.src.main:app --reload --host 0.0.0.0 --port 8000

Откройте в браузере: http://localhost:8000
```
