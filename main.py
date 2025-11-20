from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import redis
import os

app = FastAPI()

# Подключаем Redis
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/register")
async def register_user(request: Request):
    data = await request.json()
    username = data.get("username")
    email = data.get("email")

    if not username or not email:
        raise HTTPException(status_code=400, detail="Username and email are required")

    # Универсальный способ сохранения в Redis
    user_key = f"user:{username}"
    user_data = {"username": username, "email": email}

    # Удаляем старые данные если есть
    redis_client.delete(user_key)

    # Сохраняем каждое поле отдельно
    for field, value in user_data.items():
        redis_client.hset(user_key, field, value)

    return {"message": "User registered successfully"}


@app.delete("/delete/{username}")
async def delete_user(username: str):
    user_key = f"user:{username}"
    if not redis_client.exists(user_key):
        raise HTTPException(status_code=404, detail="User not found")

    redis_client.delete(user_key)
    return {"message": "User deleted successfully"}


@app.get("/check/{username}")
async def check_user(username: str):
    user_key = f"user:{username}"
    user_exists = redis_client.exists(user_key)
    return {"exists": user_exists}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)
