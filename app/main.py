from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import redis
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import socket
import uuid as uuid_lib

from app.config import config
from app.models import *
#from app.auth import get_current_user, get_user_role

app = FastAPI(title="DND Template Creator", version="1.0.0")

# Redis connection
redis_client = redis.Redis.from_url(
    config.get_redis_url(),
    decode_responses=True
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware для определения IP и аутентификации
@app.middleware("http")
async def user_identification(request: Request, call_next):
    # Получаем IP пользователя
    ip = request.client.host

    # Пробуем получить пользователя по IP
    user_key = redis_client.get(RedisKeys.user_by_ip(ip))

    if user_key:
        request.state.user = redis_client.hgetall(user_key)
        request.state.user_role = request.state.user.get("role", UserRole.GUEST)
    else:
        request.state.user = None
        request.state.user_role = UserRole.GUEST

    response = await call_next(request)
    return response


# Главная страница
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    # Получаем девиз дня
    daily_motto = redis_client.get(RedisKeys.daily_motto()) or "Вперед, герой!"

    # Получаем публичные шаблоны
    public_template_ids = redis_client.lrange(RedisKeys.public_templates(), 0, 9)
    public_templates = []

    for template_id in public_template_ids:
        template_data = redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            template_data['id'] = template_id
            # Получаем количество лайков
            likes = redis_client.scard(RedisKeys.template_likes(template_id))
            template_data['likes'] = likes
            public_templates.append(template_data)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "daily_motto": daily_motto,
            "public_templates": public_templates
        }
    )


# Страница редактора шаблонов
@app.get("/editor/{template_id?}", response_class=HTMLResponse)
async def template_editor(request: Request, template_id: Optional[str] = None):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "Для создания шаблонов необходимо войти в систему"
            }
        )

    template_data = None
    if template_id:
        template_data = redis_client.hgetall(RedisKeys.template(template_id))
        if template_data and template_data.get('owner') != user_data.get('username'):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

    return templates.TemplateResponse(
        "template_editor.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "template": template_data
        }
    )


# API для регистрации/логина
@app.post("/api/auth")
async def authenticate_user(request: Request):
    data = await request.json()
    ip = request.client.host

    # Проверяем, есть ли пользователь с таким IP
    existing_user_key = redis_client.get(RedisKeys.user_by_ip(ip))

    if existing_user_key:
        # Возвращаем существующего пользователя
        user_data = redis_client.hgetall(existing_user_key)
        return {
            "success": True,
            "user": user_data,
            "message": "Добро пожаловать обратно!"
        }

    # Создаем нового пользователя
    username = data.get("username", f"adventurer_{uuid.uuid4().hex[:8]}")
    email = data.get("email", "")

    user_key = RedisKeys.user(username)
    user_data = {
        "username": username,
        "email": email,
        "role": UserRole.USER,
        "created_at": datetime.now().isoformat(),
        "avatar": "default.png",
        "settings": json.dumps({
            "theme": "medieval",
            "font_preference": "serif",
            "default_export_format": ExportFormat.PDF.value
        })
    }

    # Сохраняем в Redis
    redis_client.hset(user_key, mapping=user_data)

    # Связываем IP с пользователем
    redis_client.set(RedisKeys.user_by_ip(ip), user_key, ex=timedelta(days=30))

    # Сохраняем IP в списке пользователя
    user_ips_key = f"{user_key}:ips"
    redis_client.sadd(user_ips_key, ip)

    return {
        "success": True,
        "user": user_data,
        "message": "Регистрация успешна!"
    }


# API для создания/сохранения шаблона
@app.post("/api/templates")
async def save_template(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    data = await request.json()
    template_id = data.get("id") or f"template_{uuid.uuid4().hex}"

    template_data = {
        "id": template_id,
        "owner": user_data["username"],
        "name": data["name"],
        "description": data.get("description", ""),
        "visibility": data.get("visibility", TemplateVisibility.PRIVATE.value),
        "content": json.dumps(data["content"]),
        "style": json.dumps(data.get("style", {})),
        "decorations": json.dumps(data.get("decorations", [])),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "character_class": data.get("character_class", ""),
        "level": data.get("level", 1),
        "tags": json.dumps(data.get("tags", []))
    }

    # Сохраняем шаблон
    redis_client.hset(RedisKeys.template(template_id), mapping=template_data)

    # Добавляем в список шаблонов пользователя
    redis_client.lpush(RedisKeys.user_templates(user_data["username"]), template_id)

    # Если шаблон публичный, добавляем в общий список
    if template_data["visibility"] == TemplateVisibility.PUBLIC.value:
        redis_client.lpush(RedisKeys.public_templates(), template_id)

    return {"success": True, "template_id": template_id}


# API для экспорта шаблона
@app.get("/api/templates/{template_id}/export/{format}")
async def export_template(template_id: str, format: ExportFormat):
    template_data = redis_client.hgetall(RedisKeys.template(template_id))

    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Здесь будет логика генерации файла
    # Пока возвращаем JSON
    if format == ExportFormat.JSON:
        return JSONResponse(content=template_data)

    # Для PDF/PNG нужно использовать дополнительные библиотеки
    # Например, reportlab для PDF, PIL для PNG
    return {"message": f"Экспорт в {format} в разработке"}


# API для лайков
@app.post("/api/templates/{template_id}/like")
async def like_template(request: Request, template_id: str):
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    # Добавляем лайк
    redis_client.sadd(RedisKeys.template_likes(template_id), user_data["username"])
    redis_client.sadd(RedisKeys.user_likes(user_data["username"]), template_id)

    return {"success": True, "likes": redis_client.scard(RedisKeys.template_likes(template_id))}


# API для добавления в коллекцию
@app.post("/api/templates/{template_id}/collect")
async def collect_template(request: Request, template_id: str):
    user_data = request.state.user

    if not user_data:
        raise HTTPException(status_code=401, detail="Требуется авторизация")

    template_data = redis_client.hgetall(RedisKeys.template(template_id))

    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Добавляем в коллекцию пользователя
    collection_item = {
        "template_id": template_id,
        "added_at": datetime.now().isoformat(),
        "original_owner": template_data["owner"]
    }

    redis_client.lpush(
        RedisKeys.user_collection(user_data["username"]),
        json.dumps(collection_item)
    )

    return {"success": True}


# Административные endpoints
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    user_data = request.state.user

    if not user_data or user_data.get("role") != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Получаем статистику
    total_users = len(redis_client.keys("user:*"))
    total_templates = len(redis_client.keys("template:*"))
    banned_users = redis_client.smembers(RedisKeys.banned_users())

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "user": user_data,
            "stats": {
                "total_users": total_users,
                "total_templates": total_templates,
                "banned_users": len(banned_users)
            }
        }
    )


@app.post("/api/admin/motto")
async def set_daily_motto(request: Request):
    user_data = request.state.user

    if not user_data or user_data.get("role") != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    data = await request.json()
    motto = data.get("motto", "")

    redis_client.set(RedisKeys.daily_motto(), motto)

    return {"success": True}


@app.post("/api/admin/promote")
async def promote_user(request: Request):
    user_data = request.state.user

    if not user_data or user_data.get("role") != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    data = await request.json()
    target_user = data.get("username")
    new_role = data.get("role")
    admin_code = data.get("admin_code")

    if new_role == UserRole.ADMIN and admin_code != config.ADMIN_CODE:
        raise HTTPException(status_code=403, detail="Неверный код администратора")

    user_key = RedisKeys.user(target_user)
    if redis_client.exists(user_key):
        redis_client.hset(user_key, "role", new_role)
        return {"success": True}

    raise HTTPException(status_code=404, detail="Пользователь не найден")


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="localhost", port=port, reload=not config.RENDER)