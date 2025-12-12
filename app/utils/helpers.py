import json
import hashlib
import socket
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import Request


def get_client_ip(request: Request) -> str:
    """Получаем IP адрес клиента"""
    if request.client:
        return request.client.host
    return "unknown"


def generate_user_id(username: str, ip: str) -> str:
    """Генерируем уникальный ID пользователя"""
    unique_string = f"{username}_{ip}_{datetime.now().isoformat()}"
    return hashlib.md5(unique_string.encode()).hexdigest()[:12]


def validate_email(email: str) -> bool:
    """Простая валидация email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def format_template_preview(template_data: Dict[str, Any]) -> Dict[str, Any]:
    """Форматирует данные шаблона для превью"""
    preview = {
        'id': template_data.get('id'),
        'name': template_data.get('name', 'Без названия'),
        'owner': template_data.get('owner', 'unknown'),
        'character_class': template_data.get('character_class', 'Не указан'),
        'level': template_data.get('level', 1),
        'created_at': template_data.get('created_at'),
        'visibility': template_data.get('visibility', 'private')
    }

    # Парсим контент для извлечения краткого описания
    try:
        content = json.loads(template_data.get('content', '{}'))
        if 'description' in content:
            preview['description'] = content['description'][:200] + '...' if len(content['description']) > 200 else \
            content['description']
    except:
        preview['description'] = template_data.get('description', '')[:200] + '...' if len(
            template_data.get('description', '')) > 200 else template_data.get('description', '')

    return preview


def calculate_modifier(attribute_value: int) -> int:
    """Рассчитывает модификатор характеристики D&D"""
    return (attribute_value - 10) // 2


def generate_dice_roll(dice: str) -> Dict[str, Any]:
    """Генерирует результат броска костей D&D"""
    # Формат: "2d6+3" или "1d20"
    import random
    import re

    pattern = r'(\d+)d(\d+)([+-]\d+)?'
    match = re.match(pattern, dice)

    if not match:
        return {"result": 0, "rolls": [], "modifier": 0}

    num_dice = int(match.group(1))
    dice_sides = int(match.group(2))
    modifier = int(match.group(3) or 0)

    rolls = [random.randint(1, dice_sides) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    return {
        "result": total,
        "rolls": rolls,
        "modifier": modifier,
        "dice": dice
    }


def sanitize_html(html: str) -> str:
    """Очищает HTML от потенциально опасных тегов"""
    import html
    return html.escape(html)


def get_file_extension(filename: str) -> str:
    """Получает расширение файла"""
    return filename.split('.')[-1].lower() if '.' in filename else ''


def is_image_file(filename: str) -> bool:
    """Проверяет, является ли файл изображением"""
    image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
    return get_file_extension(filename) in image_extensions


def format_file_size(size_bytes: int) -> str:
    """Форматирует размер файла в читаемый вид"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_browser_info(request: Request) -> Dict[str, str]:
    """Получает информацию о браузере пользователя"""
    user_agent = request.headers.get('user-agent', '')
    accept_language = request.headers.get('accept-language', '')

    return {
        'user_agent': user_agent[:200],
        'accept_language': accept_language,
        'platform': 'mobile' if 'Mobile' in user_agent else 'desktop'
    }


def generate_qr_code_data(url: str) -> str:
    """Генерирует данные для QR кода (упрощенная версия)"""
    # В реальном приложении используйте библиотеку qrcode
    return f"QR_CODE_PLACEHOLDER:{url}"


def time_ago(timestamp: str) -> str:
    """Конвертирует timestamp в читаемый формат 'сколько времени назад'"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days > 365:
            years = diff.days // 365
            return f"{years} год(а) назад"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} месяц(ев) назад"
        elif diff.days > 0:
            return f"{diff.days} день(дней) назад"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} час(а) назад"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} минут(ы) назад"
        else:
            return "только что"
    except:
        return "недавно"


def validate_dnd_class(dnd_class: str) -> bool:
    """Проверяет, является ли класс допустимым для D&D 5e"""
    valid_classes = [
        'barbarian', 'bard', 'cleric', 'druid', 'fighter',
        'monk', 'paladin', 'ranger', 'rogue', 'sorcerer',
        'warlock', 'wizard'
    ]
    return dnd_class.lower() in valid_classes


def validate_race(race: str) -> bool:
    """Проверяет, является ли раса допустимой для D&D 5e"""
    valid_races = [
        'human', 'elf', 'dwarf', 'halfling', 'gnome',
        'half-elf', 'half-orc', 'tiefling', 'dragonborn'
    ]
    return race.lower() in valid_races


def generate_template_preview(template_data: Dict[str, Any]) -> Dict[str, Any]:
    """Создает превью шаблона для отображения в галерее"""
    preview = {
        'id': template_data.get('id'),
        'name': template_data.get('name', 'Без названия'),
        'owner': template_data.get('owner', 'Неизвестно'),
        'character_class': template_data.get('character_class'),
        'level': template_data.get('level', 1),
        'likes': 0,
        'comments': 0,
        'created_at': template_data.get('created_at'),
        'preview_color': '#4a6572'  # Цвет по умолчанию
    }

    # Определяем цвет на основе класса
    class_colors = {
        'barbarian': '#c41e3a',
        'bard': '#f58cba',
        'cleric': '#ffffff',
        'druid': '#ff7d0a',
        'fighter': '#c69b6d',
        'monk': '#00ff96',
        'paladin': '#f48cba',
        'ranger': '#aad372',
        'rogue': '#fff569',
        'sorcerer': '#69ccf0',
        'warlock': '#9482c9',
        'wizard': '#3c8ce7'
    }

    if template_data.get('character_class'):
        preview['preview_color'] = class_colors.get(
            template_data['character_class'].lower(),
            '#4a6572'
        )

    return preview
