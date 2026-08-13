from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://warehouse:warehouse@db:5432/warehouse"
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b"
    api_key: str = "dev-secret-key-123"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()