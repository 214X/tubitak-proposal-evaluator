from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "TUBITAK Proposal Evaluator API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    upload_storage_dir: Path = Path("runtime/uploads")
    upload_session_timeout_seconds: int = 120
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )


settings = Settings()
