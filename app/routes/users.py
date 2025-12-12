from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import json
from datetime import datetime, timedelta
import uuid
from typing import Optional

from app.models import *
from app.utils.helpers import get_client_ip, validate_email

router = APIRouter()


@router.post("/auth")
async def authenticate_user(request: Request):
    """Аутентификация пользователя по IP"""
    try:
        data = await request.json()
    except:
        data = {}

    ip = get_client_ip(request)

    # Проверяем существующего пользователя по IP
    existing_user_key = request.app.redis_client.get(RedisKeys.user_by_ip(ip))

    if existing_user_key:
        user_data = request.app.redis_client.hgetall(existing_user_key)
        if user_data:
            # Обновляем время последнего входа
            request.app.redis_client.hset(
                existing_user_key,
                "last_login",
                datetime.now().isoformat()
            )

            return {
                "success": True,
                "user": user_data,
                "message": "Добро пожаловать обратно!",
                "redirect": "/dashboard"
            }

    # Создаем нового пользователя
    username = data.get("username", "")
    email = data.get("email", "")

    # Генерируем имя пользователя если не указано
    if not username:
        username = f"adventurer_{uuid.uuid4().hex[:8]}"

    # Проверяем email если указан
    if email and not validate_email(email):
        return {
            "success": False,
            "message": "Неверный формат email"
        }

    # Проверяем, не занято ли имя
    user_key = RedisKeys.user(username)
    if request.app.redis_client.exists(user_key):
        return {
            "success": False,
            "message": "Имя пользователя уже занято"
        }

    # Создаем данные пользователя
    user_data = {
        "username": username,
        "email": email,
        "role": UserRole.USER.value,
        "created_at": datetime.now().isoformat(),
        "last_login": datetime.now().isoformat(),
        "avatar": "default.png",
        "settings": json.dumps({
            "theme": "dark",
            "font_size": "medium",
            "notifications": True,
            "default_view": "grid"
        })
    }

    # Сохраняем пользователя (старый синтаксис hset)
    for field, value in user_data.items():
        request.app.redis_client.hset(user_key, field, value)

    # Связываем IP с пользователем
    request.app.redis_client.set(
        RedisKeys.user_by_ip(ip),
        user_key,
        ex=timedelta(days=30)
    )

    # Сохраняем IP в списке пользователя
    user_ips_key = f"{user_key}:ips"
    request.app.redis_client.sadd(user_ips_key, ip)

    return {
        "success": True,
        "user": user_data,
        "message": "Регистрация успешна!",
        "redirect": "/dashboard"
    }


@router.post("/logout")
async def logout_user(request: Request):
    """Выход пользователя из системы"""
    # Для IP-базированной аутентификации просто очищаем куки/локальное хранилище
    return {
        "success": True,
        "message": "Вы вышли из системы",
        "redirect": "/"
    }


@router.get("/profile/{username}")
async def get_user_profile(username: str, request: Request):
    """Получает профиль пользователя"""
    user_data = request.app.redis_client.hgetall(RedisKeys.user(username))

    if not user_data:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем статистику пользователя
    user_templates = request.app.redis_client.lrange(
        RedisKeys.user_templates(username),
        0, -1
    )

    # Получаем лайки пользователя
    liked_templates = list(request.app.redis_client.smembers(
        RedisKeys.user_likes(username)
    ))

    return {
        "profile": user_data,
        "stats": {
            "templates_count": len(user_templates),
            "likes_received": 0,  # Можно рассчитать позже
            "collection_count": request.app.redis_client.llen(
                RedisKeys.user_collection(username)
            )
        },
        "recent_templates": user_templates[:5]
    }


@router.put("/profile")
async def update_user_profile(request: Request):
    """Обновляет профиль пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        update_data = await request.json()
    except:
        update_data = {}

    user_key = RedisKeys.user(user_data["username"])
    current_data = request.app.redis_client.hgetall(user_key)

    # Разрешаем обновлять только определенные поля
    allowed_fields = ["email", "avatar", "settings"]

    for field in allowed_fields:
        if field in update_data:
            if field == "settings":
                # Объединяем настройки
                current_settings = json.loads(current_data.get("settings", "{}"))
                new_settings = update_data[field]
                if isinstance(new_settings, dict):
                    current_settings.update(new_settings)
                    request.app.redis_client.hset(
                        user_key,
                        field,
                        json.dumps(current_settings)
                    )
            else:
                request.app.redis_client.hset(user_key, field, update_data[field])

    # Обновляем время последнего изменения
    request.app.redis_client.hset(
        user_key,
        "updated_at",
        datetime.now().isoformat()
    )

    return {
        "success": True,
        "message": "Профиль обновлен"
    }


@router.post("/ip/add")
async def add_ip_address(request: Request):
    """Добавляет IP адрес к аккаунту пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        data = await request.json()
    except:
        data = {}

    ip_to_add = data.get("ip")

    if not ip_to_add:
        raise HTTPException(status_code=400, detail="IP адрес не указан")

    user_key = RedisKeys.user(user_data["username"])
    user_ips_key = f"{user_key}:ips"

    # Добавляем IP в список пользователя
    request.app.redis_client.sadd(user_ips_key, ip_to_add)

    # Связываем IP с пользователем
    request.app.redis_client.set(
        RedisKeys.user_by_ip(ip_to_add),
        user_key,
        ex=timedelta(days=30)
    )

    return {
        "success": True,
        "message": "IP адрес добавлен"
    }


@router.delete("/ip/remove")
async def remove_ip_address(request: Request):
    """Удаляет IP адрес из аккаунта пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        data = await request.json()
    except:
        data = {}

    ip_to_remove = data.get("ip")

    if not ip_to_remove:
        raise HTTPException(status_code=400, detail="IP адрес не указан")

    user_key = RedisKeys.user(user_data["username"])
    user_ips_key = f"{user_key}:ips"

    # Удаляем IP из списка пользователя
    request.app.redis_client.srem(user_ips_key, ip_to_remove)

    # Удаляем связь IP с пользователем
    request.app.redis_client.delete(RedisKeys.user_by_ip(ip_to_remove))

    return {
        "success": True,
        "message": "IP адрес удален"
    }


@router.get("/ips")
async def get_user_ips(request: Request):
    """Получает список IP адресов пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    user_key = RedisKeys.user(user_data["username"])
    user_ips_key = f"{user_key}:ips"

    user_ips = list(request.app.redis_client.smembers(user_ips_key))

    return {
        "ips": user_ips,
        "count": len(user_ips)
    }


@router.delete("/account")
async def delete_account(request: Request):
    """Удаляет аккаунт пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    username = user_data["username"]
    user_key = RedisKeys.user(username)

    # Удаляем все связанные данные
    # 1. Удаляем пользователя
    request.app.redis_client.delete(user_key)

    # 2. Удаляем IP связи
    user_ips_key = f"{user_key}:ips"
    user_ips = request.app.redis_client.smembers(user_ips_key)
    for ip in user_ips:
        request.app.redis_client.delete(RedisKeys.user_by_ip(ip))
    request.app.redis_client.delete(user_ips_key)

    # 3. Помечаем шаблоны как удаленные
    user_templates = request.app.redis_client.lrange(
        RedisKeys.user_templates(username),
        0, -1
    )
    for template_id in user_templates:
        request.app.redis_client.hset(
            RedisKeys.template(template_id),
            "deleted",
            "true"
        )
        request.app.redis_client.hset(
            RedisKeys.template(template_id),
            "deleted_at",
            datetime.now().isoformat()
        )

    # 4. Удаляем коллекции и лайки
    request.app.redis_client.delete(RedisKeys.user_templates(username))
    request.app.redis_client.delete(RedisKeys.user_collection(username))
    request.app.redis_client.delete(RedisKeys.user_likes(username))

    return {
        "success": True,
        "message": "Аккаунт удален",
        "redirect": "/"
    }


@router.get("/activity")
async def get_user_activity(request: Request):
    """Получает активность пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    username = user_data["username"]

    # Получаем последние действия
    activity = []

    # Недавно созданные шаблоны
    recent_templates = request.app.redis_client.lrange(
        RedisKeys.user_templates(username),
        0, 4
    )

    for template_id in recent_templates:
        template = request.app.redis_client.hgetall(RedisKeys.template(template_id))
        if template:
            activity.append({
                "type": "template_created",
                "template_id": template_id,
                "template_name": template.get("name", "Без названия"),
                "timestamp": template.get("created_at", datetime.now().isoformat()),
                "icon": "📝"
            })

    # Недавние лайки
    liked_templates = list(request.app.redis_client.smembers(
        RedisKeys.user_likes(username)
    ))[:5]

    for template_id in liked_templates:
        template = request.app.redis_client.hgetall(RedisKeys.template(template_id))
        if template:
            activity.append({
                "type": "template_liked",
                "template_id": template_id,
                "template_name": template.get("name", "Без названия"),
                "author": template.get("owner", "Неизвестно"),
                "timestamp": datetime.now().isoformat(),
                "icon": "❤️"
            })

    # Сортируем по времени
    activity.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    return {
        "activity": activity[:10]  # Последние 10 действий
    }


@router.get("/stats")
async def get_user_stats(request: Request):
    """Получает статистику пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    username = user_data["username"]

    # Количество шаблонов
    templates_count = request.app.redis_client.llen(RedisKeys.user_templates(username))

    # Количество лайков
    liked_count = request.app.redis_client.scard(RedisKeys.user_likes(username))

    # Количество в коллекции
    collection_count = request.app.redis_client.llen(RedisKeys.user_collection(username))

    # Получаем полученные лайки (упрощенно)
    received_likes = 0
    user_templates = request.app.redis_client.lrange(RedisKeys.user_templates(username), 0, -1)
    for template_id in user_templates:
        likes = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
        received_likes += likes

    return {
        "templates_created": templates_count,
        "templates_liked": liked_count,
        "collection_items": collection_count,
        "likes_received": received_likes,
        "account_age_days": 0  # Можно рассчитать
    }


@router.post("/avatar")
async def update_avatar(request: Request):
    """Обновляет аватар пользователя"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    try:
        data = await request.json()
    except:
        data = {}

    avatar = data.get("avatar")

    if not avatar:
        raise HTTPException(status_code=400, detail="Аватар не указан")

    user_key = RedisKeys.user(user_data["username"])
    request.app.redis_client.hset(user_key, "avatar", avatar)

    return {
        "success": True,
        "message": "Аватар обновлен",
        "avatar": avatar
    }


@router.get("/check/{username}")
async def check_username(username: str, request: Request):
    """Проверяет, занято ли имя пользователя"""
    user_key = RedisKeys.user(username)
    exists = request.app.redis_client.exists(user_key)

    return {
        "username": username,
        "available": not exists
    }


@router.get("/current")
async def get_current_user(request: Request):
    """Получает информацию о текущем пользователе"""
    user_data = request.state.user

    if not user_data:
        return {
            "authenticated": False,
            "user": None
        }

    return {
        "authenticated": True,
        "user": user_data
    }