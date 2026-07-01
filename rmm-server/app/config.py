"""Application configuration loaded from environment variables."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "RMM Server"
    ENV: str = "development"
    DEBUG: bool = True

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8765  # WebSocket + API port (per system docs)

    # --- Database (async SQLAlchemy + asyncpg) ---
    POSTGRES_USER: str = "rmm"
    POSTGRES_PASSWORD: str = "rmm"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "rmm"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # --- Auth / JWT ---
    JWT_SECRET: str = "CHANGE_ME_IN_PRODUCTION_use_openssl_rand_hex_32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12h admin sessions

    # Length (bytes) of per-machine agent enrollment tokens
    AGENT_TOKEN_BYTES: int = 32

    # --- CORS (Electron admin app origins) ---
    CORS_ORIGINS: list[str] = ["*"]

    # --- Heartbeat ---
    # Seconds without a heartbeat before an agent is considered offline.
    AGENT_OFFLINE_AFTER: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
