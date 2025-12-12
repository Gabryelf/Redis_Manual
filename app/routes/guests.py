from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import json
from datetime import datetime
from typing import Optional, List

from app.models import *

router = APIRouter()


@router.get("/templates")
async def get_public_templates(
        request: Request,
        page: int = 1,
        limit: int = 20,
        class_filter: Optional[str] = None,
        sort_by: str = "newest"
):
    """Получение публичных шаблонов для гостей"""
    per_page = min(limit, 50)  # Ограничиваем максимальное количество
    start = (page - 1) * per_page

    # Получаем все публичные шаблоны
    template_ids = request.app.redis_client.lrange(RedisKeys.public_templates(), 0, -1)

    templates_list = []
    for template_id in template_ids:
        template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            template_data['id'] = template_id
            template_data['likes'] = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
            templates_list.append(template_data)

    # Фильтрация по классу
    if class_filter:
        templates_list = [t for t in templates_list if t.get('character_class') == class_filter]

    # Сортировка
    if sort_by == "popular":
        templates_list.sort(key=lambda x: x.get('likes', 0), reverse=True)
    elif sort_by == "oldest":
        templates_list.sort(key=lambda x: x.get('created_at', ''))
    else:  # newest
        templates_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)

    # Пагинация
    total = len(templates_list)
    paginated_templates = templates_list[start:start + per_page]

    # Преобразуем JSON строки
    for template in paginated_templates:
        try:
            if 'content' in template:
                template['content'] = json.loads(template['content'])
            if 'style' in template:
                template['style'] = json.loads(template['style'])
            if 'tags' in template:
                template['tags'] = json.loads(template['tags'])
        except:
            pass

    return {
        "templates": paginated_templates,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_more": start + per_page < total
    }


@router.get("/template/{template_id}")
async def get_template_details(request: Request, template_id: str):
    """Получение деталей шаблона для гостей"""
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))

    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    visibility = template_data.get('visibility', TemplateVisibility.PRIVATE.value)
    if visibility != TemplateVisibility.PUBLIC.value:
        raise HTTPException(status_code=403, detail="Этот шаблон не публичный")

    # Преобразуем JSON строки
    try:
        if 'content' in template_data:
            template_data['content'] = json.loads(template_data['content'])
        if 'style' in template_data:
            template_data['style'] = json.loads(template_data['style'])
        if 'tags' in template_data:
            template_data['tags'] = json.loads(template_data['tags'])
        if 'decorations' in template_data:
            template_data['decorations'] = json.loads(template_data['decorations'])
    except:
        pass

    # Получаем статистику
    template_data['likes'] = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
    template_data['comments_count'] = request.app.redis_client.llen(RedisKeys.template_comments(template_id))

    # Получаем комментарии (только первые 10 для гостей)
    comments = request.app.redis_client.lrange(RedisKeys.template_comments(template_id), 0, 9)
    parsed_comments = []
    for comment in comments:
        try:
            parsed_comments.append(json.loads(comment))
        except:
            pass

    # Получаем информацию о владельце (только публичные данные)
    owner_info = {}
    owner = template_data.get('owner')
    if owner:
        owner_data = request.app.redis_client.hgetall(RedisKeys.user(owner))
        if owner_data:
            owner_info = {
                "username": owner_data.get("username", "unknown"),
                "avatar": owner_data.get("avatar", "default.png")
            }

    return {
        "template": template_data,
        "comments": parsed_comments,
        "owner_info": owner_info
    }


@router.get("/template/{template_id}/preview")
async def get_template_preview(request: Request, template_id: str):
    """Получение превью шаблона для гостей"""
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))

    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    visibility = template_data.get('visibility', TemplateVisibility.PRIVATE.value)
    if visibility != TemplateVisibility.PUBLIC.value:
        raise HTTPException(status_code=403, detail="Этот шаблон не публичный")

    # Создаем упрощенное превью
    preview = {
        "id": template_id,
        "name": template_data.get("name", "Без названия"),
        "description": template_data.get("description", "")[:200],
        "owner": template_data.get("owner", "Неизвестно"),
        "character_class": template_data.get("character_class", ""),
        "level": template_data.get("level", 1),
        "likes": request.app.redis_client.scard(RedisKeys.template_likes(template_id)),
        "created_at": template_data.get("created_at"),
        "visibility": visibility
    }

    try:
        tags = template_data.get("tags")
        if tags:
            preview["tags"] = json.loads(tags)
        else:
            preview["tags"] = []
    except:
        preview["tags"] = []

    return preview


@router.get("/classes")
async def get_dnd_classes(request: Request):
    """Получение списка классов D&D"""
    return {
        "classes": [
            {"id": "barbarian", "name": "Варвар"},
            {"id": "bard", "name": "Бард"},
            {"id": "cleric", "name": "Жрец"},
            {"id": "druid", "name": "Друид"},
            {"id": "fighter", "name": "Воин"},
            {"id": "monk", "name": "Монах"},
            {"id": "paladin", "name": "Паладин"},
            {"id": "ranger", "name": "Следопыт"},
            {"id": "rogue", "name": "Плут"},
            {"id": "sorcerer", "name": "Чародей"},
            {"id": "warlock", "name": "Колдун"},
            {"id": "wizard", "name": "Волшебник"}
        ]
    }


@router.get("/stats")
async def get_public_stats(request: Request):
    """Получение публичной статистики"""
    total_templates = len(request.app.redis_client.keys("template:*"))

    # Подсчитываем публичные шаблоны
    public_template_ids = request.app.redis_client.lrange(RedisKeys.public_templates(), 0, -1)
    public_templates_count = len(public_template_ids)

    # Подсчитываем пользователей (примерно)
    user_keys = request.app.redis_client.keys("user:*")
    total_users = len([k for k in user_keys if ":ips" not in k and ":templates" not in k])

    # Самый популярный шаблон
    most_liked = None
    max_likes = 0

    for template_id in public_template_ids[:100]:  # Проверяем первые 100
        likes = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
        if likes > max_likes:
            max_likes = likes
            template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
            if template_data:
                most_liked = {
                    "id": template_id,
                    "name": template_data.get("name", "Без названия"),
                    "owner": template_data.get("owner", "Неизвестно"),
                    "likes": likes
                }

    return {
        "total_templates": total_templates,
        "public_templates": public_templates_count,
        "total_users": total_users,
        "most_liked_template": most_liked,
        "daily_motto": request.app.redis_client.get(RedisKeys.daily_motto()) or "Добро пожаловать!"
    }


@router.get("/search")
async def search_templates(
        request: Request,
        q: Optional[str] = None,
        page: int = 1,
        limit: int = 20
):
    """Поиск шаблонов по названию и описанию"""
    per_page = min(limit, 50)
    start = (page - 1) * per_page

    if not q or len(q.strip()) < 2:
        return {
            "templates": [],
            "page": page,
            "per_page": per_page,
            "total": 0,
            "has_more": False
        }

    query = q.lower().strip()

    # Получаем все публичные шаблоны
    template_ids = request.app.redis_client.lrange(RedisKeys.public_templates(), 0, -1)

    matching_templates = []
    for template_id in template_ids:
        template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            # Проверяем совпадение
            name = template_data.get("name", "").lower()
            description = template_data.get("description", "").lower()
            character_class = template_data.get("character_class", "").lower()

            if (query in name or
                    query in description or
                    query in character_class):
                template_data['id'] = template_id
                template_data['likes'] = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
                matching_templates.append(template_data)

    # Пагинация
    total = len(matching_templates)
    paginated_templates = matching_templates[start:start + per_page]

    return {
        "templates": paginated_templates,
        "query": q,
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_more": start + per_page < total
    }
