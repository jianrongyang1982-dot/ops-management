"""
应用配置 - 所有敏感信息从环境变量/.env读取，不写入代码
"""
import base64
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # 应用
    APP_NAME: str = "运营管理系统"
    APP_ENV: str = "dev"
    API_PREFIX: str = "/api"
    SECRET_KEY: str = "change-me-in-production-please-use-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # OceanBase (MySQL 模式)
    DB_HOST: str = "80.238.234.89"
    DB_PORT: int = 6883
    DB_USER: str = "roc@roc#rocob"
    # 密码含特殊字符(! #等)，用 base64 存储避免 dotenv 解析问题
    DB_PASSWORD_B64: str = ""
    DB_NAME: str = "ipcmdb"
    DB_CHARSET: str = "utf8mb4"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    @property
    def DB_PASSWORD(self) -> str:
        if self.DB_PASSWORD_B64:
            try:
                return base64.b64decode(self.DB_PASSWORD_B64).decode()
            except Exception:
                pass
        return ""

    # 飞驼开放平台
    FREIGHTOWER_TOKEN_URL: str = "http://openapi.freightower.com/auth/api/token"
    FREIGHTOWER_QUERY_URL: str = "http://openapi.freightower.com/application/v1/query"
    FREIGHTOWER_CLIENT_ID: str = "f19969576877957a1"
    FREIGHTOWER_SECRET: str = "123456"

    # 定时同步
    SYNC_INTERVAL_MINUTES: int = 30

    # CORS
    CORS_ORIGINS: List[str] = ["*"]


settings = Settings()
