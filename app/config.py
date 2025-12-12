import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Redis configuration
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

    # App configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ADMIN_CODE = os.getenv("ADMIN_CODE", "dnd-master-2024")

    # Render.com specific
    RENDER = os.getenv("RENDER", "false").lower() == "true"

    @classmethod
    def get_redis_url(cls):
        if cls.REDIS_PASSWORD:
            return f"redis://:{cls.REDIS_PASSWORD}@{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"
        return f"redis://{cls.REDIS_HOST}:{cls.REDIS_PORT}/{cls.REDIS_DB}"


config = Config()
