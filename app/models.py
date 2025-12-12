from enum import Enum


class UserRole(str, Enum):
    GUEST = "guest"
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class TemplateVisibility(str, Enum):
    PRIVATE = "private"
    PUBLIC = "public"
    UNLISTED = "unlisted"


class ExportFormat(str, Enum):
    PDF = "pdf"
    PNG = "png"
    JSON = "json"


# Redis keys structure
class RedisKeys:
    @staticmethod
    def user(username: str) -> str:
        return f"user:{username}"

    @staticmethod
    def user_by_ip(ip: str) -> str:
        return f"user_ip:{ip}"

    @staticmethod
    def user_by_mac(mac: str) -> str:
        return f"user_mac:{mac}"

    @staticmethod
    def template(template_id: str) -> str:
        return f"template:{template_id}"

    @staticmethod
    def user_templates(username: str) -> str:
        return f"user:{username}:templates"

    @staticmethod
    def public_templates() -> str:
        return "templates:public"

    @staticmethod
    def template_likes(template_id: str) -> str:
        return f"template:{template_id}:likes"

    @staticmethod
    def template_comments(template_id: str) -> str:
        return f"template:{template_id}:comments"

    @staticmethod
    def user_likes(username: str) -> str:
        return f"user:{username}:liked_templates"

    @staticmethod
    def user_collection(username: str) -> str:
        return f"user:{username}:collection"

    @staticmethod
    def daily_motto() -> str:
        return "app:daily_motto"

    @staticmethod
    def banned_users() -> str:
        return "app:banned_users"
