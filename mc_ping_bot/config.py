from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Конфигурация приложения, загружаемая из переменных окружения или файла .env.
    """
    bot_token: str
    db_dsn: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/mc_ping"
    redis_url: str = "redis://localhost:6379/0"
    admin_chat_id: int = 0
    commands_version: str = "v1"

    # Настройки Pydantic для чтения .env файла
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

# Экземпляр конфигурации
config = Settings()
