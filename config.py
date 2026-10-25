"""
Cấu hình hệ thống – đọc từ biến môi trường.
Nâng cấp code không ảnh hưởng dữ liệu vì schema do Alembic quản lý.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    APP_NAME: str = "Hệ thống Kết nối Huyết thống qua ADN"
    VERSION: str = "4.0.0"
    COPYRIGHT: str = "Phan Quý Vinh – 0975898828"

    # Database – ƯU TIÊN PostgreSQL để dữ liệu không mất khi nâng cấp / redeploy
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dna_data.db")

    # Bảo mật
    ADMIN_API_KEY: str = os.getenv(
        "ADMIN_API_KEY", "PhanQuyVinh_ChangeMe_In_Production_2026"
    )
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")  # Fernet key

    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    ALLOWED_ORIGINS: list = os.getenv("ALLOWED_ORIGINS", "*").split(",")

    # Rate limit
    RATE_LIMIT: str = "30/minute"

    @property
    def is_postgres(self) -> bool:
        url = self.DATABASE_URL.lower()
        return url.startswith("postgres")

    @property
    def sqlalchemy_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
