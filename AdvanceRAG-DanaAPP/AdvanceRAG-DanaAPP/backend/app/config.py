from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    default_llm_base_url: str = "https://api.gapgpt.app/v1"
    default_llm_model: str = "gapgpt-qwen-3.6"
    default_embedding_model: str = "text-embedding-3-small"
    default_llm_api_key: str = ""

    max_upload_mb: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
