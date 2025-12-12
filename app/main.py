from fastapi import FastAPI, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis
import json
import uuid
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import hashlib
import socket
import mimetypes
from pathlib import Path

from app.config import config
from app.models import *
from app.utils.helpers import get_client_ip


# ============ LIFESPAN HANDLER (заменяем on_event) ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Запуск DND Template Creator...")

    # Создаем дефолтного администратора если его нет
    admin_key = RedisKeys.user("admin")
    if not redis_client.exists(admin_key):
        admin_data = {
            "username": "admin",
            "email": "admin@dndforge.com",
            "role": UserRole.ADMIN.value,
            "created_at": datetime.now().isoformat(),
            "avatar": "admin.png",
            "settings": json.dumps({"theme": "dark"})
        }
        # Используем правильный синтаксис для hset
        for field, value in admin_data.items():
            redis_client.hset(admin_key, field, value)
        print("✅ Создан администратор по умолчанию")

    # Устанавливаем дефолтный девиз дня если его нет
    if not redis_client.exists(RedisKeys.daily_motto()):
        redis_client.set(RedisKeys.daily_motto(), "Добро пожаловать в кузницу шаблонов D&D!")

    # Создаем дефолтные изображения если их нет
    images_dir = Path("app/static/images")
    images_dir.mkdir(parents=True, exist_ok=True)

    # Создаем дефолтный CSS если его нет
    css_file = Path("app/static/css/style.css")
    if not css_file.exists():
        create_default_css()

    # Создаем дефолтный JS если его нет
    js_file = Path("app/static/js/main.js")
    if not js_file.exists():
        create_default_js()

    print("✅ Приложение готово к работе!")

    yield

    # Shutdown
    print("👋 Завершение работы приложения...")
    redis_client.close()


# ============ ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ============
app = FastAPI(
    title="DND Template Creator",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# ============ ПОДКЛЮЧЕНИЕ К REDIS ============
try:
    redis_client = redis.Redis(
        host=config.REDIS_HOST,
        port=config.REDIS_PORT,
        db=config.REDIS_DB,
        password=config.REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True
    )
    # Тестируем соединение
    redis_client.ping()
    print("✅ Redis подключен успешно")
except (redis.ConnectionError, redis.AuthenticationError) as e:
    print(f"⚠️ Не удалось подключиться к Redis: {e}. Используем временное хранилище.")


    # Временное хранилище в памяти для разработки
    class MemoryStorage:
        def __init__(self):
            self.data = {}
            self.sets = {}
            self.lists = {}

        def hset(self, name, key=None, value=None, mapping=None):
            if name not in self.data:
                self.data[name] = {}

            if mapping:
                # Поддержка mapping для совместимости
                self.data[name].update(mapping)
                return len(mapping)
            elif key is not None and value is not None:
                self.data[name][key] = value
                return 1
            return 0

        def hgetall(self, name):
            return self.data.get(name, {})

        def get(self, name):
            return self.data.get(name)

        def set(self, name, value, ex=None):
            self.data[name] = value
            return True

        def exists(self, name):
            return name in self.data

        def delete(self, *names):
            count = 0
            for name in names:
                if name in self.data:
                    del self.data[name]
                    count += 1
            return count

        def sadd(self, name, *values):
            if name not in self.sets:
                self.sets[name] = set()
            self.sets[name].update(values)
            return len(values)

        def scard(self, name):
            return len(self.sets.get(name, set()))

        def srem(self, name, *values):
            if name in self.sets:
                for value in values:
                    self.sets[name].discard(value)
            return 1

        def smembers(self, name):
            return list(self.sets.get(name, set()))

        def sismember(self, name, value):
            return value in self.sets.get(name, set())

        def lpush(self, name, *values):
            if name not in self.lists:
                self.lists[name] = []
            self.lists[name] = list(values) + self.lists[name]
            return len(self.lists[name])

        def lrange(self, name, start, end):
            lst = self.lists.get(name, [])
            if end < 0:
                end = len(lst)
            return lst[start:end + 1]

        def lrem(self, name, count, value):
            if name not in self.lists:
                return 0
            lst = self.lists[name]
            removed = 0
            if count == 0:
                # Удаляем все вхождения
                while value in lst:
                    lst.remove(value)
                    removed += 1
            elif count > 0:
                # Удаляем первые count вхождений
                for _ in range(count):
                    if value in lst:
                        lst.remove(value)
                        removed += 1
            else:
                # Удаляем последние |count| вхождений
                for _ in range(abs(count)):
                    if value in lst:
                        lst.reverse()
                        lst.remove(value)
                        lst.reverse()
                        removed += 1
            return removed

        def llen(self, name):
            return len(self.lists.get(name, []))

        def keys(self, pattern):
            import re
            # Простая замена * на .*
            pattern = pattern.replace('*', '.*')
            pattern = pattern.replace('?', '.')
            regex = re.compile(f"^{pattern}$")
            return [k for k in list(self.data.keys()) + list(self.sets.keys()) + list(self.lists.keys()) if
                    regex.match(k)]


    redis_client = MemoryStorage()

# Добавляем redis_client к app для доступа в маршрутах
app.redis_client = redis_client

# ============ НАСТРОЙКА ПУТЕЙ ============
# Создаем статические директории если их нет
static_dir = Path("app/static")
static_dir.mkdir(parents=True, exist_ok=True)
(static_dir / "images").mkdir(exist_ok=True)
(static_dir / "css").mkdir(exist_ok=True)
(static_dir / "js").mkdir(exist_ok=True)
(static_dir / "avatars").mkdir(exist_ok=True)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ============ MIDDLEWARE ============
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
    ip = get_client_ip(request)

    # Проверяем, не забанен ли IP
    banned_ips = redis_client.smembers(RedisKeys.banned_users())
    if ip in banned_ips:
        return HTMLResponse(
            content="""
            <html>
                <body style="text-align: center; padding: 50px; font-family: Arial;">
                    <h1>🚫 Доступ запрещен</h1>
                    <p>Ваш IP адрес заблокирован.</p>
                </body>
            </html>
            """,
            status_code=403
        )

    # Пробуем получить пользователя по IP
    user_key = redis_client.get(RedisKeys.user_by_ip(ip))

    if user_key:
        user_data = redis_client.hgetall(user_key)
        if user_data:
            # Проверяем не забанен ли пользователь
            if redis_client.sismember(RedisKeys.banned_users(), user_data.get("username", "")):
                request.state.user = None
                request.state.user_role = UserRole.GUEST
            else:
                request.state.user = user_data
                request.state.user_role = user_data.get("role", UserRole.GUEST.value)
        else:
            request.state.user = None
            request.state.user_role = UserRole.GUEST.value
    else:
        request.state.user = None
        request.state.user_role = UserRole.GUEST.value

    response = await call_next(request)
    return response


# ============ РЕГИСТРАЦИЯ МАРШРУТОВ ============
# Импортируем и регистрируем маршруты
try:
    from app.routes import users, templates_routes, admin, guests

    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(templates_routes.router, prefix="/api/templates", tags=["templates"])
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(guests.router, prefix="/api/guests", tags=["guests"])
    print("✅ Маршруты API загружены")
except ImportError as e:
    print(f"⚠️  Не удалось загрузить маршруты: {e}")
    print("ℹ️  Создайте файлы в директории app/routes/")


# ============ ОСНОВНЫЕ МАРШРУТЫ HTML ============
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    # Получаем девиз дня
    daily_motto = redis_client.get(RedisKeys.daily_motto()) or "Вперед, герой!"

    # Получаем топ публичные шаблоны
    public_template_ids = redis_client.lrange(RedisKeys.public_templates(), 0, 11)
    public_templates = []

    for template_id in public_template_ids:
        template_data = redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            # Преобразуем JSON строки обратно в объекты
            try:
                if 'content' in template_data:
                    template_data['content'] = json.loads(template_data['content'])
                if 'style' in template_data:
                    template_data['style'] = json.loads(template_data['style'])
                if 'tags' in template_data:
                    template_data['tags'] = json.loads(template_data['tags'])
            except:
                pass

            template_data['id'] = template_id
            # Получаем количество лайков
            likes = redis_client.scard(RedisKeys.template_likes(template_id))
            template_data['likes'] = likes
            # Получаем количество комментариев
            comments_count = redis_client.llen(RedisKeys.template_comments(template_id))
            template_data['comments_count'] = comments_count

            public_templates.append(template_data)

    # Статистика для показа
    total_templates = len(redis_client.keys("template:*"))
    total_users = len(redis_client.keys("user:*"))

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "daily_motto": daily_motto,
            "public_templates": public_templates[:6],
            "stats": {
                "total_templates": total_templates,
                "total_users": total_users
            }
        }
    )


@app.get("/gallery", response_class=HTMLResponse)
async def gallery(request: Request,
                  page: int = 1,
                  class_filter: Optional[str] = None,
                  sort_by: str = "newest"):
    per_page = 12
    start = (page - 1) * per_page

    # Получаем все публичные шаблоны
    template_ids = redis_client.lrange(RedisKeys.public_templates(), 0, -1)

    templates_list = []
    for template_id in template_ids:
        template_data = redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            template_data['id'] = template_id
            template_data['likes'] = redis_client.scard(RedisKeys.template_likes(template_id))
            templates_list.append(template_data)

    # Фильтрация
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
    total_pages = max(1, (len(templates_list) + per_page - 1) // per_page)
    paginated_templates = templates_list[start:start + per_page]

    return templates.TemplateResponse(
        "gallery.html",
        {
            "request": request,
            "user": request.state.user,
            "role": request.state.user_role,
            "templates": paginated_templates,
            "page": page,
            "total_pages": total_pages,
            "class_filter": class_filter,
            "sort_by": sort_by,
            "classes": ["Воин", "Волшебник", "Жрец", "Плут", "Варвар", "Паладин", "Следопыт", "Друид", "Бард", "Монах"]
        }
    )


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST.value:
        return RedirectResponse("/?message=login_required")

    # Получаем шаблоны пользователя
    user_templates_ids = redis_client.lrange(
        RedisKeys.user_templates(user_data["username"]),
        0, 19
    )

    user_templates = []
    for template_id in user_templates_ids:
        template_data = redis_client.hgetall(RedisKeys.template(template_id))
        if template_data:
            template_data['id'] = template_id
            template_data['likes'] = redis_client.scard(RedisKeys.template_likes(template_id))
            user_templates.append(template_data)

    # Получаем коллекцию пользователя
    collection_items = redis_client.lrange(
        RedisKeys.user_collection(user_data["username"]),
        0, 9
    )

    collection_templates = []
    for item in collection_items:
        try:
            item_data = json.loads(item)
            template_data = redis_client.hgetall(
                RedisKeys.template(item_data.get('template_id'))
            )
            if template_data:
                template_data['id'] = item_data.get('template_id')
                template_data['added_at'] = item_data.get('added_at')
                collection_templates.append(template_data)
        except:
            continue

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "user_templates": user_templates,
            "collection_templates": collection_templates,
            "recent_activity": []
        }
    )


@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST.value:
        return RedirectResponse("/?message=login_required")

    # Получаем связанные IP адреса
    user_ips_key = f"user:{user_data['username']}:ips"
    user_ips = list(redis_client.smembers(user_ips_key))

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "user_ips": user_ips,
            "avatar_list": [
                "warrior.png", "wizard.png", "rogue.png", "cleric.png",
                "dragon.png", "knight.png", "elf.png", "dwarf.png"
            ]
        }
    )


@app.get("/editor", response_class=HTMLResponse)
async def editor_new(request: Request):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST.value:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "Для создания шаблонов необходимо войти в систему",
                "redirect_url": "/editor"
            }
        )

    return templates.TemplateResponse(
        "template_editor.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "template": None,
            "is_edit": False,
            "dnd_classes": [
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
            ],
            "races": [
                "Человек", "Эльф", "Дварф", "Халфлинг", "Гном",
                "Полуэльф", "Полуорк", "Тифлинг", "Драконорожденный"
            ]
        }
    )


@app.get("/editor/{template_id}", response_class=HTMLResponse)
async def editor_edit(request: Request, template_id: str):
    user_data = request.state.user
    role = request.state.user_role

    if role == UserRole.GUEST.value:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "message": "Для редактирования шаблонов необходимо войти в систему",
                "redirect_url": f"/editor/{template_id}"
            }
        )

    template_data = redis_client.hgetall(RedisKeys.template(template_id))
    if template_data:
        # Проверяем права доступа
        if template_data.get('owner') != user_data.get('username'):
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Декодируем JSON поля
        try:
            if 'content' in template_data:
                template_data['content'] = json.loads(template_data['content'])
            if 'style' in template_data:
                template_data['style'] = json.loads(template_data['style'])
            if 'decorations' in template_data:
                template_data['decorations'] = json.loads(template_data['decorations'])
            if 'tags' in template_data:
                template_data['tags'] = json.loads(template_data['tags'])
        except:
            pass

    return templates.TemplateResponse(
        "template_editor.html",
        {
            "request": request,
            "user": user_data,
            "role": role,
            "template": template_data,
            "is_edit": True,
            "dnd_classes": [
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
            ],
            "races": [
                "Человек", "Эльф", "Дварф", "Халфлинг", "Гном",
                "Полуэльф", "Полуорк", "Тифлинг", "Драконорожденный"
            ]
        }
    )


@app.get("/template/{template_id}", response_class=HTMLResponse)
async def view_template(request: Request, template_id: str):
    template_data = redis_client.hgetall(RedisKeys.template(template_id))

    if not template_data:
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # Проверяем видимость
    visibility = template_data.get('visibility', TemplateVisibility.PRIVATE.value)
    user_data = request.state.user

    if visibility == TemplateVisibility.PRIVATE.value:
        if not user_data or user_data.get('username') != template_data.get('owner'):
            raise HTTPException(status_code=403, detail="Этот шаблон приватный")

    # Декодируем JSON поля
    try:
        if 'content' in template_data:
            template_data['content'] = json.loads(template_data['content'])
        if 'style' in template_data:
            template_data['style'] = json.loads(template_data['style'])
        if 'decorations' in template_data:
            template_data['decorations'] = json.loads(template_data['decorations'])
        if 'tags' in template_data:
            template_data['tags'] = json.loads(template_data['tags'])
    except:
        pass

    # Получаем лайки и комментарии
    likes = redis_client.scard(RedisKeys.template_likes(template_id))
    comments = redis_client.lrange(RedisKeys.template_comments(template_id), 0, 49)

    # Парсим комментарии
    parsed_comments = []
    for comment in comments:
        try:
            parsed_comments.append(json.loads(comment))
        except:
            pass

    # Проверяем лайкнул ли текущий пользователь
    user_liked = False
    if user_data:
        user_liked = redis_client.sismember(
            RedisKeys.template_likes(template_id),
            user_data.get('username')
        )

    # Проверяем в коллекции ли у пользователя
    in_collection = False
    if user_data:
        collection_items = redis_client.lrange(
            RedisKeys.user_collection(user_data["username"]),
            0, -1
        )
        for item in collection_items:
            try:
                item_data = json.loads(item)
                if item_data.get('template_id') == template_id:
                    in_collection = True
                    break
            except:
                continue

    return templates.TemplateResponse(
        "template_view.html",
        {
            "request": request,
            "user": user_data,
            "role": request.state.user_role,
            "template": template_data,
            "likes": likes,
            "comments": parsed_comments,
            "user_liked": user_liked,
            "in_collection": in_collection,
            "owner_info": redis_client.hgetall(
                RedisKeys.user(template_data.get('owner', ''))
            ) if template_data.get('owner') else {}
        }
    )


# ============ ВСПОМОГАТЕЛЬНЫЕ МАРШРУТЫ ============
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, message: Optional[str] = None):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "message": message,
            "user": request.state.user
        }
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel_page(request: Request):
    user_data = request.state.user

    if not user_data or user_data.get("role") not in [UserRole.ADMIN.value, UserRole.MODERATOR.value]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    # Статистика
    total_users = len([k for k in redis_client.keys("user:*") if ":ips" not in k and ":templates" not in k])
    total_templates = len(redis_client.keys("template:*"))
    banned_users = redis_client.smembers(RedisKeys.banned_users())

    # Последние 10 пользователей
    recent_users = []
    user_keys = redis_client.keys("user:*")
    for key in user_keys[:10]:
        if ":ips" not in key and ":templates" not in key:
            user = redis_client.hgetall(key)
            if user:
                recent_users.append(user)

    # Последние 10 шаблонов
    recent_templates = []
    template_ids = redis_client.lrange(RedisKeys.public_templates(), 0, 9)
    for template_id in template_ids:
        template = redis_client.hgetall(RedisKeys.template(template_id))
        if template:
            template['id'] = template_id
            recent_templates.append(template)

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "user": user_data,
            "role": user_data.get("role"),
            "stats": {
                "total_users": total_users,
                "total_templates": total_templates,
                "banned_users": len(banned_users),
                "public_templates": len(template_ids)
            },
            "recent_users": recent_users,
            "recent_templates": recent_templates,
            "is_admin": user_data.get("role") == UserRole.ADMIN.value
        }
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(
        "about.html",
        {
            "request": request,
            "user": request.state.user,
            "role": request.state.user_role
        }
    )


# ============ СТАТИЧЕСКИЕ ФАЙЛЫ ============
@app.get("/images/{filename}")
async def get_image(filename: str):
    image_path = Path(f"app/static/images/{filename}")
    if image_path.exists():
        return FileResponse(image_path)
    raise HTTPException(status_code=404, detail="Image not found")


@app.get("/avatars/{filename}")
async def get_avatar(filename: str):
    avatar_path = Path(f"app/static/avatars/{filename}")
    if avatar_path.exists():
        return FileResponse(avatar_path)

    # Если файла нет, возвращаем дефолтный
    default_path = Path("app/static/avatars/default.png")
    if default_path.exists():
        return FileResponse(default_path)

    # Создаем простой дефолтный аватар
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        img = Image.new('RGB', (100, 100), color='#8b4513')
        d = ImageDraw.Draw(img)
        d.ellipse([10, 10, 90, 90], fill='#d4af37')

        # Пробуем использовать шрифт, если есть
        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except:
            font = ImageFont.load_default()

        d.text((50, 50), "?", fill='black', anchor='mm', font=font)

        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)

        # Сохраняем для будущего использования
        default_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(default_path)

        return FileResponse(default_path)
    except ImportError:
        # Если PIL не установлен, возвращаем 404
        raise HTTPException(status_code=404, detail="Avatar not found")


# ============ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ============
def create_default_css():
    """Создает дефолтный CSS файл"""
    css_content = """/* Основные стили для D&D Template Creator */
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #e6e6e6; min-height: 100vh; }
.container { max-width: 1400px; margin: 0 auto; padding: 0 20px; }
.navbar { display: flex; justify-content: space-between; align-items: center; padding: 1rem 0; border-bottom: 2px solid #0f3460; margin-bottom: 2rem; }
.nav-brand h1 { color: #e94560; font-size: 1.8rem; }
.nav-links { display: flex; gap: 1.5rem; align-items: center; }
.nav-link { color: #e6e6e6; text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; transition: all 0.3s ease; }
.nav-link:hover { background: rgba(233, 69, 96, 0.1); color: #e94560; }
.btn { padding: 0.75rem 1.5rem; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; text-decoration: none; display: inline-block; }
.btn-primary { background: linear-gradient(45deg, #e94560, #ff7b54); color: white; }
.btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(233, 69, 96, 0.4); }
.btn-secondary { background: rgba(255, 255, 255, 0.1); color: white; border: 1px solid rgba(255, 255, 255, 0.2); }
.btn-secondary:hover { background: rgba(255, 255, 255, 0.2); }
.template-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 1.5rem; margin: 2rem 0; }
.template-card { background: rgba(255, 255, 255, 0.05); border-radius: 12px; overflow: hidden; transition: all 0.3s ease; border: 1px solid rgba(255, 255, 255, 0.1); }
.template-card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3); border-color: #e94560; }
.template-preview { height: 200px; background: linear-gradient(135deg, #0f3460, #1a1a2e); display: flex; align-items: center; justify-content: center; }
.template-info { padding: 1.5rem; }
.template-title { font-size: 1.2rem; font-weight: 600; margin-bottom: 0.5rem; color: white; }
.template-author { color: #a0a0a0; font-size: 0.9rem; margin-bottom: 1rem; }
.message { padding: 1rem; border-radius: 8px; margin: 1rem 0; }
.message-success { background: rgba(46, 204, 113, 0.2); border: 1px solid #2ecc71; color: #2ecc71; }
.message-error { background: rgba(231, 76, 60, 0.2); border: 1px solid #e74c3c; color: #e74c3c; }
.message-warning { background: rgba(241, 196, 15, 0.2); border: 1px solid #f1c40f; color: #f1c40f; }
.form-group { margin-bottom: 1.5rem; }
.form-label { display: block; margin-bottom: 0.5rem; font-weight: 600; color: #e6e6e6; }
.form-input { width: 100%; padding: 0.75rem; background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 8px; color: white; font-size: 1rem; }
.form-input:focus { outline: none; border-color: #e94560; box-shadow: 0 0 0 3px rgba(233, 69, 96, 0.2); }
@media (max-width: 768px) { .navbar { flex-direction: column; gap: 1rem; } .nav-links { flex-wrap: wrap; justify-content: center; } .template-grid { grid-template-columns: 1fr; } }
@media (max-width: 480px) { .nav-brand h1 { font-size: 1.5rem; } .btn { padding: 0.6rem 1.2rem; font-size: 0.9rem; } .template-preview { height: 150px; } }"""

    css_file = Path("app/static/css/style.css")
    css_file.parent.mkdir(parents=True, exist_ok=True)
    css_file.write_text(css_content, encoding='utf-8')


def create_default_js():
    """Создает дефолтный JS файл"""
    js_content = """// Основной JavaScript для DND Template Creator
document.addEventListener('DOMContentLoaded', function() {
    console.log('DND Template Creator loaded');

    // Простая функция для показа сообщений
    window.showMessage = function(text, type = 'info') {
        const messageEl = document.createElement('div');
        messageEl.className = 'message message-' + type;
        messageEl.textContent = text;
        document.body.appendChild(messageEl);
        setTimeout(() => messageEl.remove(), 5000);
    };

    // Обработка формы входа
    const authForm = document.getElementById('auth-form');
    if (authForm) {
        authForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const formData = new FormData(this);
            try {
                const response = await fetch('/api/users/auth', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(Object.fromEntries(formData))
                });
                const data = await response.json();
                if (data.success) {
                    showMessage(data.message, 'success');
                    setTimeout(() => window.location.href = data.redirect || '/', 1500);
                } else {
                    showMessage(data.message, 'error');
                }
            } catch (error) {
                showMessage('Ошибка соединения', 'error');
            }
        });
    }
});"""

    js_file = Path("app/static/js/main.js")
    js_file.parent.mkdir(parents=True, exist_ok=True)
    js_file.write_text(js_content, encoding='utf-8')


# ============ ТОЧКА ВХОДА ============
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "app.main:app",
        host="localhost",
        port=port,
        reload=not config.RENDER,
        log_level="info"
    )
