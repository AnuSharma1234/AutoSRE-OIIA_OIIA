from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str
    database_url: str
    redis_url: str
    kubeconfig: str | None = None
    cluster_id: str
    api_secret_key: str
    auto_execute_low_threshold: float = 0.9
    auto_execute_medium_threshold: float = 0.9


settings = Settings()
