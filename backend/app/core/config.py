from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "TUBITAK Proposal Evaluator API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"


settings = Settings()
