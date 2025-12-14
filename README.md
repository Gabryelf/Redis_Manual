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

| Интерфейс управления репозиториями | Создание Issue с шаблоном |
|-----------------------------------|----------------------------|
| ![Управление репозиториями](https://via.placeholder.com/600x400/0d1117/238636?text=Repository+Dashboard) | ![Создание Issue](https://via.placeholder.com/600x400/0d1117/6e40c9?text=Template+Selection) |

| Предпросмотр Markdown | История активности |
|-----------------------|---------------------|
| ![Предпросмотр](https://via.placeholder.com/600x400/0d1117/8b949e?text=Markdown+Preview) | ![Активность](https://via.placeholder.com/600x400/0d1117/da3633?text=Activity+Log) |

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
