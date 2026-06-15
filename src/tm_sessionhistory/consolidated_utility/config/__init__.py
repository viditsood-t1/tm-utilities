"""
consolidated_utility.config
-----------------------------
Centralised configuration loaded from environment variables or a .env file.
All database connection strings live here so every module uses the same source
of truth.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings  # pydantic v2 style

load_dotenv()


class Settings(BaseSettings):
    # ── PostgreSQL ──────────────────────────────────────────────────────────
    postgres_host:     str = Field("localhost",          env="POSTGRES_HOST")
    postgres_port:     int = Field(5432,                 env="POSTGRES_PORT")
    postgres_db:       str = Field("utility_db",         env="POSTGRES_DB")
    postgres_user:     str = Field("postgres",           env="POSTGRES_USER")
    postgres_password: str = Field("postgres",           env="POSTGRES_PASSWORD")

    # ── MongoDB ─────────────────────────────────────────────────────────────
    mongo_uri:        str = Field("mongodb://localhost:27017", env="MONGO_URI")
    mongo_db:         str = Field("utility_db",               env="MONGO_DB")
    mongo_collection: str = Field("sessions",                 env="MONGO_COLLECTION")

    # ── General ─────────────────────────────────────────────────────────────
    log_level:         str = Field("INFO", env="LOG_LEVEL")
    default_page_size: int = Field(20,     env="DEFAULT_PAGE_SIZE")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
