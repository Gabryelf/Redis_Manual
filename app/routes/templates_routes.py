from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
import json
from datetime import datetime, timedelta
import uuid
from typing import Optional, List
import io

from app.models import *

router = APIRouter()


@router.post("")
async def create_template(request: Request):
    """Создание нового шаблона"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        data = await request.json()
    except:
        data = {}

    template_id = data.get("id") or f"template_{uuid.uuid4().hex}"

    template_data = {
        "id": template_id,
        "owner": user_data["username"],
        "name": data.get("name", "Новый шаблон"),
        "description": data.get("description", ""),
        "visibility": data.get("visibility", TemplateVisibility.PRIVATE.value),
        "content": json.dumps(data.get("content", {})),
        "style": json.dumps(data.get("style", {})),
        "decorations": json.dumps(data.get("decorations", [])),
        "character_class": data.get("character_class", ""),
        "level": data.get("level", 1),
        "tags": json.dumps(data.get("tags", [])),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }

    # Сохраняем шаблон
    for field, value in template_data.items():
        request.app.redis_client.hset(RedisKeys.template(template_id), field, value)

    # Добавляем в список шаблонов пользователя
    request.app.redis_client.lpush(RedisKeys.user_templates(user_data["username"]), template_id)

    # Если шаблон публичный, добавляем в общий список
    if template_data["visibility"] == TemplateVisibility.PUBLIC.value:
        request.app.redis_client.lpush(RedisKeys.public_templates(), template_id)

    return {"success": True, "template_id": template_id}


@router.put("/{template_id}")
async def update_template(request: Request, template_id: str):
    """Обновление существующего шаблона"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверяем права на редактирование
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    if template_data.get("owner") != user_data["username"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    try:
        data = await request.json()
    except:
        data = {}

    update_fields = {
        "name": data.get("name"),
        "description": data.get("description"),
        "visibility": data.get("visibility"),
        "content": json.dumps(data.get("content", {})) if "content" in data else None,
        "style": json.dumps(data.get("style", {})) if "style" in data else None,
        "decorations": json.dumps(data.get("decorations", [])) if "decorations" in data else None,
        "character_class": data.get("character_class"),
        "level": data.get("level"),
        "tags": json.dumps(data.get("tags", [])) if "tags" in data else None,
        "updated_at": datetime.now().isoformat()
    }

    # Обновляем только указанные поля
    old_visibility = template_data.get("visibility")

    for field, value in update_fields.items():
        if value is not None:
            request.app.redis_client.hset(RedisKeys.template(template_id), field, value)

    # Обновляем публичный список если изменилась видимость
    new_visibility = data.get("visibility", old_visibility)
    if new_visibility != old_visibility:
        if new_visibility == TemplateVisibility.PUBLIC.value:
            # Добавляем в публичный список если его там нет
            public_templates = request.app.redis_client.lrange(RedisKeys.public_templates(), 0, -1)
            if template_id not in public_templates:
                request.app.redis_client.lpush(RedisKeys.public_templates(), template_id)
        else:
            # Удаляем из публичного списка
            request.app.redis_client.lrem(RedisKeys.public_templates(), 0, template_id)

    return {"success": True, "message": "Шаблон обновлен"}


@router.delete("/{template_id}")
async def delete_template(request: Request, template_id: str):
    """Удаление шаблона"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверяем права на удаление
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    if template_data.get("owner") != user_data["username"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    # Удаляем шаблон
    request.app.redis_client.delete(RedisKeys.template(template_id))

    # Удаляем из списка пользователя
    request.app.redis_client.lrem(RedisKeys.user_templates(user_data["username"]), 0, template_id)

    # Удаляем из публичного списка
    request.app.redis_client.lrem(RedisKeys.public_templates(), 0, template_id)

    # Удаляем лайки
    request.app.redis_client.delete(RedisKeys.template_likes(template_id))

    # Удаляем комментарии
    request.app.redis_client.delete(RedisKeys.template_comments(template_id))

    return {"success": True, "message": "Шаблон удален"}


@router.post("/{template_id}/like")
async def like_template(request: Request, template_id: str):
    """Лайк шаблона"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    username = user_data["username"]

    # Проверяем существование шаблона
    if not request.app.redis_client.exists(RedisKeys.template(template_id)):
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if template_data.get("visibility") == TemplateVisibility.PRIVATE.value:
        if template_data.get("owner") != username:
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    # Добавляем лайк
    request.app.redis_client.sadd(RedisKeys.template_likes(template_id), username)
    request.app.redis_client.sadd(RedisKeys.user_likes(username), template_id)

    likes_count = request.app.redis_client.scard(RedisKeys.template_likes(template_id))

    return {"success": True, "likes": likes_count}


@router.delete("/{template_id}/like")
async def unlike_template(request: Request, template_id: str):
    """Удаление лайка с шаблона"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    username = user_data["username"]

    # Удаляем лайк
    request.app.redis_client.srem(RedisKeys.template_likes(template_id), username)
    request.app.redis_client.srem(RedisKeys.user_likes(username), template_id)

    likes_count = request.app.redis_client.scard(RedisKeys.template_likes(template_id))

    return {"success": True, "likes": likes_count}


@router.post("/{template_id}/collect")
async def collect_template(request: Request, template_id: str):
    """Добавление шаблона в коллекцию"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверяем существование шаблона
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    if template_data.get("visibility") == TemplateVisibility.PRIVATE.value:
        if template_data.get("owner") != user_data["username"]:
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    # Проверяем, не добавлен ли уже
    collection_items = request.app.redis_client.lrange(
        RedisKeys.user_collection(user_data["username"]),
        0, -1
    )

    for item in collection_items:
        try:
            item_data = json.loads(item)
            if item_data.get("template_id") == template_id:
                return {"success": False, "message": "Шаблон уже в коллекции"}
        except:
            continue

    # Добавляем в коллекцию
    collection_item = {
        "template_id": template_id,
        "added_at": datetime.now().isoformat(),
        "original_owner": template_data["owner"],
        "template_name": template_data.get("name", "Без названия")
    }

    request.app.redis_client.lpush(
        RedisKeys.user_collection(user_data["username"]),
        json.dumps(collection_item)
    )

    return {"success": True, "message": "Добавлено в коллекцию"}


@router.delete("/{template_id}/collect")
async def remove_from_collection(request: Request, template_id: str):
    """Удаление шаблона из коллекции"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Ищем и удаляем из коллекции
    collection_items = request.app.redis_client.lrange(
        RedisKeys.user_collection(user_data["username"]),
        0, -1
    )

    removed = False
    for item in collection_items:
        try:
            item_data = json.loads(item)
            if item_data.get("template_id") == template_id:
                request.app.redis_client.lrem(
                    RedisKeys.user_collection(user_data["username"]),
                    0, item
                )
                removed = True
                break
        except:
            continue

    if not removed:
        raise HTTPException(status_code=404, detail="Шаблон не найден в коллекции")

    return {"success": True, "message": "Удалено из коллекции"}


@router.post("/{template_id}/comment")
async def add_comment(request: Request, template_id: str):
    """Добавление комментария к шаблону"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверяем существование шаблона
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    if template_data.get("visibility") == TemplateVisibility.PRIVATE.value:
        if template_data.get("owner") != user_data["username"]:
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    try:
        data = await request.json()
    except:
        data = {}

    comment_text = data.get("text", "").strip()

    if not comment_text:
        raise HTTPException(status_code=400, detail="Комментарий не может быть пустым")

    if len(comment_text) > 1000:
        raise HTTPException(status_code=400, detail="Комментарий слишком длинный")

    comment = {
        "id": f"comment_{uuid.uuid4().hex}",
        "author": user_data["username"],
        "text": comment_text,
        "created_at": datetime.now().isoformat()
    }

    # Добавляем комментарий
    request.app.redis_client.lpush(
        RedisKeys.template_comments(template_id),
        json.dumps(comment)
    )

    return {"success": True, "comment": comment}


@router.delete("/{template_id}/comment/{comment_id}")
async def delete_comment(request: Request, template_id: str, comment_id: str):
    """Удаление комментария"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Проверяем комментарии
    comments = request.app.redis_client.lrange(
        RedisKeys.template_comments(template_id),
        0, -1
    )

    for i, comment_str in enumerate(comments):
        try:
            comment = json.loads(comment_str)
            if comment.get("id") == comment_id:
                # Проверяем права (автор или админ)
                if comment.get("author") == user_data["username"] or \
                        user_data.get("role") in [UserRole.ADMIN.value, UserRole.MODERATOR.value]:
                    # Удаляем комментарий
                    request.app.redis_client.lrem(
                        RedisKeys.template_comments(template_id),
                        0, comment_str
                    )
                    return {"success": True, "message": "Комментарий удален"}
                else:
                    raise HTTPException(status_code=403, detail="Недостаточно прав")
        except:
            continue

    raise HTTPException(status_code=404, detail="Комментарий не найден")


@router.get("/{template_id}/comments")
async def get_comments(request: Request, template_id: str, limit: int = 50):
    """Получение комментариев к шаблону"""
    # Проверяем существование шаблона
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    visibility = template_data.get("visibility", TemplateVisibility.PRIVATE.value)
    user_data = request.state.user

    if visibility == TemplateVisibility.PRIVATE.value:
        if not user_data or user_data.get("username") != template_data.get("owner"):
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    # Получаем комментарии
    comments = request.app.redis_client.lrange(
        RedisKeys.template_comments(template_id),
        0, limit - 1
    )

    parsed_comments = []
    for comment in comments:
        try:
            parsed_comments.append(json.loads(comment))
        except:
            continue

    return {
        "template_id": template_id,
        "comments": parsed_comments,
        "count": len(parsed_comments)
    }


@router.get("/{template_id}/likes")
async def get_likes(request: Request, template_id: str):
    """Получение списка пользователей, лайкнувших шаблон"""
    # Проверяем существование шаблона
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    visibility = template_data.get("visibility", TemplateVisibility.PRIVATE.value)
    user_data = request.state.user

    if visibility == TemplateVisibility.PRIVATE.value:
        if not user_data or user_data.get("username") != template_data.get("owner"):
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    # Получаем лайки
    likes = list(request.app.redis_client.smembers(RedisKeys.template_likes(template_id)))

    return {
        "template_id": template_id,
        "likes": likes,
        "count": len(likes)
    }


@router.get("/user/{username}")
async def get_user_templates(request: Request, username: str, limit: int = 20):
    """Получение шаблонов пользователя"""
    user_key = RedisKeys.user(username)
    if not request.app.redis_client.exists(user_key):
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user_data = request.app.redis_client.hgetall(user_key)

    # Проверяем, можно ли показывать шаблоны
    user_templates_ids = request.app.redis_client.lrange(
        RedisKeys.user_templates(username),
        0, limit - 1
    )

    templates = []
    current_user = request.state.user
    is_owner = current_user and current_user.get("username") == username

    for template_id in user_templates_ids:
        template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            # Проверяем видимость
            visibility = template_data.get("visibility", TemplateVisibility.PRIVATE.value)
            if visibility == TemplateVisibility.PUBLIC.value or is_owner:
                template_data['id'] = template_id
                template_data['likes'] = request.app.redis_client.scard(RedisKeys.template_likes(template_id))

                # Декодируем JSON поля
                try:
                    if 'content' in template_data:
                        template_data['content'] = json.loads(template_data['content'])
                    if 'style' in template_data:
                        template_data['style'] = json.loads(template_data['style'])
                    if 'tags' in template_data:
                        template_data['tags'] = json.loads(template_data['tags'])
                except:
                    pass

                templates.append(template_data)

    return {
        "username": username,
        "templates": templates,
        "count": len(templates)
    }
