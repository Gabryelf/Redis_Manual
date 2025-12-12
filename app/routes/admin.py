from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
import json
from datetime import datetime, timedelta
import uuid
from typing import Optional, List

from app.models import *
from app.config import config

router = APIRouter()


def verify_admin(request: Request):
    """Проверка прав администратора"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    if user_data.get("role") not in [UserRole.ADMIN.value, UserRole.MODERATOR.value]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    return user_data


def verify_super_admin(request: Request):
    """Проверка прав суперадминистратора"""
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    if user_data.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Требуются права администратора")

    return user_data


@router.post("/motto")
async def set_daily_motto(request: Request):
    """Установка девиза дня"""
    user_data = verify_admin(request)

    try:
        data = await request.json()
    except:
        data = {}

    motto = data.get("motto", "")

    if not motto:
        raise HTTPException(status_code=400, detail="Девиз не может быть пустым")

    if len(motto) > 500:
        raise HTTPException(status_code=400, detail="Девиз слишком длинный")

    request.app.redis_client.set(RedisKeys.daily_motto(), motto)

    return {"success": True, "message": "Девиз дня обновлен"}


@router.get("/motto")
async def get_daily_motto(request: Request):
    """Получение текущего девиза дня"""
    user_data = verify_admin(request)

    motto = request.app.redis_client.get(RedisKeys.daily_motto()) or "Добро пожаловать!"

    return {"motto": motto}


@router.post("/promote")
async def promote_user(request: Request):
    """Повышение пользователя до администратора/модератора"""
    user_data = verify_super_admin(request)

    try:
        data = await request.json()
    except:
        data = {}

    target_user = data.get("username")
    new_role = data.get("role")
    admin_code = data.get("admin_code")

    if not target_user or not new_role:
        raise HTTPException(status_code=400, detail="Не указаны необходимые данные")

    # Проверяем допустимость роли
    if new_role not in [UserRole.ADMIN.value, UserRole.MODERATOR.value, UserRole.USER.value]:
        raise HTTPException(status_code=400, detail="Недопустимая роль")

    # Проверяем код администратора для назначения админа
    if new_role == UserRole.ADMIN.value:
        if admin_code != config.ADMIN_CODE:
            raise HTTPException(status_code=403, detail="Неверный код администратора")

    user_key = RedisKeys.user(target_user)
    if not request.app.redis_client.exists(user_key):
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Получаем текущую роль
    current_role = request.app.redis_client.hget(user_key, "role")
    if current_role == UserRole.ADMIN.value and new_role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Нельзя понизить администратора")

    # Обновляем роль
    request.app.redis_client.hset(user_key, "role", new_role)

    # Записываем в историю
    admin_action = {
        "action": "promote_user",
        "admin": user_data["username"],
        "target_user": target_user,
        "old_role": current_role,
        "new_role": new_role,
        "timestamp": datetime.now().isoformat()
    }

    admin_actions_key = "admin:actions"
    request.app.redis_client.lpush(admin_actions_key, json.dumps(admin_action))

    return {"success": True, "message": f"Роль пользователя изменена на {new_role}"}


@router.post("/ban")
async def ban_user(request: Request):
    """Блокировка пользователя"""
    user_data = verify_admin(request)

    try:
        data = await request.json()
    except:
        data = {}

    username = data.get("username")
    reason = data.get("reason", "Нарушение правил")

    if not username:
        raise HTTPException(status_code=400, detail="Не указано имя пользователя")

    # Проверяем существование пользователя
    user_key = RedisKeys.user(username)
    if not request.app.redis_client.exists(user_key):
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нельзя забанить другого администратора (кроме суперадмина)
    target_user = request.app.redis_client.hgetall(user_key)
    if target_user.get("role") == UserRole.ADMIN.value and user_data.get("role") != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Нельзя забанить администратора")

    # Нельзя забанить себя
    if username == user_data["username"]:
        raise HTTPException(status_code=400, detail="Нельзя забанить себя")

    # Добавляем в список забаненных
    request.app.redis_client.sadd(RedisKeys.banned_users(), username)

    # Записываем историю банов
    ban_record = {
        "username": username,
        "banned_by": user_data["username"],
        "reason": reason,
        "banned_at": datetime.now().isoformat()
    }

    ban_history_key = f"ban_history:{username}"
    request.app.redis_client.lpush(ban_history_key, json.dumps(ban_record))

    # Отправляем все IP пользователя в бан
    user_ips_key = f"{user_key}:ips"
    user_ips = request.app.redis_client.smembers(user_ips_key)
    for ip in user_ips:
        request.app.redis_client.sadd(RedisKeys.banned_users(), ip)

    return {"success": True, "message": f"Пользователь {username} заблокирован"}


@router.post("/unban")
async def unban_user(request: Request):
    """Разблокировка пользователя"""
    user_data = verify_admin(request)

    try:
        data = await request.json()
    except:
        data = {}

    username = data.get("username")

    if not username:
        raise HTTPException(status_code=400, detail="Не указано имя пользователя")

    # Проверяем, забанен ли пользователь
    if not request.app.redis_client.sismember(RedisKeys.banned_users(), username):
        return {"success": False, "message": "Пользователь не забанен"}

    # Удаляем из списка забаненных
    request.app.redis_client.srem(RedisKeys.banned_users(), username)

    # Записываем в историю
    unban_record = {
        "username": username,
        "unbanned_by": user_data["username"],
        "unbanned_at": datetime.now().isoformat()
    }

    ban_history_key = f"ban_history:{username}"
    request.app.redis_client.lpush(ban_history_key, json.dumps(unban_record))

    return {"success": True, "message": f"Пользователь {username} разблокирован"}


@router.delete("/template/{template_id}")
async def delete_template_admin(request: Request, template_id: str):
    """Удаление шаблона администратором"""
    user_data = verify_admin(request)

    # Проверяем существование шаблона
    template_data = request.app.redis_client.hgetall(RedisKeys.template(template_id))
    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    owner = template_data.get("owner", "unknown")

    # Удаляем шаблон
    request.app.redis_client.delete(RedisKeys.template(template_id))

    # Удаляем из списка пользователя
    if owner:
        request.app.redis_client.lrem(RedisKeys.user_templates(owner), 0, template_id)

    # Удаляем из публичного списка
    request.app.redis_client.lrem(RedisKeys.public_templates(), 0, template_id)

    # Удаляем лайки и комментарии
    request.app.redis_client.delete(RedisKeys.template_likes(template_id))
    request.app.redis_client.delete(RedisKeys.template_comments(template_id))

    # Записываем в историю действий администратора
    admin_action = {
        "action": "delete_template",
        "admin": user_data["username"],
        "template_id": template_id,
        "template_name": template_data.get("name", "Без названия"),
        "owner": owner,
        "timestamp": datetime.now().isoformat()
    }

    admin_actions_key = "admin:actions"
    request.app.redis_client.lpush(admin_actions_key, json.dumps(admin_action))

    return {"success": True, "message": "Шаблон удален администратором"}


@router.get("/stats")
async def get_admin_stats(request: Request):
    """Получение статистики для администратора"""
    user_data = verify_admin(request)

    # Общая статистика
    user_keys = request.app.redis_client.keys("user:*")
    total_users = len([k for k in user_keys if ":ips" not in k and ":templates" not in k])

    total_templates = len(request.app.redis_client.keys("template:*"))

    banned_users = list(request.app.redis_client.smembers(RedisKeys.banned_users()))

    # Активность за последние 24 часа
    recent_templates = request.app.redis_client.lrange(RedisKeys.public_templates(), 0, 99)
    recent_templates_count = len(recent_templates)

    # Пользователи за последние 24 часа
    recent_users = []
    for user_key in user_keys[:100]:  # Проверяем первые 100
        if ":ips" not in user_key and ":templates" not in user_key:
            user = request.app.redis_client.hgetall(user_key)
            if user:
                created_at = user.get("created_at")
                if created_at:
                    try:
                        created_dt = datetime.fromisoformat(created_at)
                        if (datetime.now() - created_dt).days < 1:
                            recent_users.append(user.get("username", "unknown"))
                    except:
                        pass

    return {
        "stats": {
            "total_users": total_users,
            "total_templates": total_templates,
            "banned_users": len(banned_users),
            "recent_templates": recent_templates_count,
            "recent_users": len(recent_users)
        },
        "banned_users": banned_users[:50],
        "recent_users": recent_users[:50]
    }


@router.get("/users")
async def get_users_list(request: Request, page: int = 1, limit: int = 20):
    """Получение списка пользователей"""
    user_data = verify_admin(request)

    user_keys = request.app.redis_client.keys("user:*")
    # Фильтруем только ключи пользователей
    user_keys = [k for k in user_keys if ":ips" not in k and ":templates" not in k]

    # Пагинация
    start = (page - 1) * limit
    end = start + limit

    users = []
    for user_key in user_keys[start:end]:
        user = request.app.redis_client.hgetall(user_key)
        if user:
            # Добавляем статистику
            username = user.get("username", "unknown")
            templates_count = request.app.redis_client.llen(RedisKeys.user_templates(username))
            is_banned = request.app.redis_client.sismember(RedisKeys.banned_users(), username)

            user["templates_count"] = templates_count
            user["is_banned"] = is_banned
            users.append(user)

    return {
        "users": users,
        "page": page,
        "limit": limit,
        "total": len(user_keys),
        "has_more": end < len(user_keys)
    }


@router.get("/templates")
async def get_templates_list(request: Request, page: int = 1, limit: int = 20):
    """Получение списка шаблонов для админки"""
    user_data = verify_admin(request)

    template_keys = request.app.redis_client.keys("template:*")

    # Пагинация
    start = (page - 1) * limit
    end = start + limit

    templates = []
    for template_key in template_keys[start:end]:
        template = request.app.redis_client.hgetall(template_key)
        if template:
            template_id = template_key.split(":")[1] if ":" in template_key else template_key
            template["id"] = template_id
            template["likes"] = request.app.redis_client.scard(RedisKeys.template_likes(template_id))
            template["comments_count"] = request.app.redis_client.llen(RedisKeys.template_comments(template_id))
            templates.append(template)

    return {
        "templates": templates,
        "page": page,
        "limit": limit,
        "total": len(template_keys),
        "has_more": end < len(template_keys)
    }


@router.get("/activity")
async def get_admin_activity(request: Request, limit: int = 50):
    """Получение действий администраторов"""
    user_data = verify_admin(request)

    admin_actions_key = "admin:actions"
    actions = request.app.redis_client.lrange(admin_actions_key, 0, limit - 1)

    parsed_actions = []
    for action in actions:
        try:
            parsed_actions.append(json.loads(action))
        except:
            continue

    return {
        "actions": parsed_actions,
        "count": len(parsed_actions)
    }