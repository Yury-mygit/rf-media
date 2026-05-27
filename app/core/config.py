from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    service_name: str = "media-dev"
    version: str = "0.1.0"
    log_level: str = "info"

    database_url: str
    storage_root: str = "/srv/storage"
    max_upload_bytes: int = 10485760
    allowed_mime_prefixes: str = "image/,audio/,video/,application/pdf,application/zip"
    cors_allow_origins: str = ""

    # GC
    media_consumers: str = ""  # "board=http://board_dev_app:8000/api/v1/media-refs;notes=..."
    media_gc_token: str = ""
    media_gc_grace_days: int = 7
    media_gc_enabled: bool = True
    media_gc_cron_hour: int = 3  # UTC

    @property
    def allowed_mime_list(self) -> list[str]:
        return [s.strip() for s in self.allowed_mime_prefixes.split(",") if s.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [s.strip() for s in self.cors_allow_origins.split(",") if s.strip()]

    @property
    def consumer_list(self) -> list[tuple[str, str]]:
        out = []
        for pair in self.media_consumers.split(";"):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                continue
            name, url = pair.split("=", 1)
            out.append((name.strip(), url.strip()))
        return out


settings = Settings()
