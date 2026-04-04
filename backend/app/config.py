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

    # --- Trigger Service / Event Poller ---
    spacetimedb_url: str = ""
    spacetimedb_module: str = ""
    spacetimedb_token: str = ""
    k8s_namespace: str = "default"
    k8s_in_cluster: str = "false"
    prometheus_url: str = ""
    alertmanager_webhook_secret: str = ""
    superplane_webhook_url: str = ""
    superplane_api_key: str = ""
    service_port: int = 8001
    log_level: str = "info"


settings = Settings()

