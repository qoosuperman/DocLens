from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    extraction_max_retries: int = 2
    database_url: str = "postgresql://doclens:doclens@localhost:5432/doclens"
