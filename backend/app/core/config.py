from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    app_name: str = "TUBITAK Proposal Evaluator API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    upload_storage_dir: Path = Path("runtime/uploads")
    embedding_storage_dir: Path = Path("runtime/embedding/chroma")
    embedding_model_cache_dir: Path = Path("cache/embedding/model-cache")
    embedding_model_name: str = "BAAI/bge-m3"
    embedding_model_max_length: int = 1024
    evaluation_rubric_path: Path = Path("app/services/evaluation/schemas/tubitak_default.json")
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model_name: str = "aya-expanse:8b"
    ollama_request_timeout_seconds: int = 120
    ollama_temperature: float = 0.0
    # Hakeme giden tek kanıt bloğundaki maksimum chunk sayısı ve chunk başına karakter sınırı.
    # Düşük değerler 8B modelde bağlam kaymasını (context drift) ve süreyi azaltır.
    judge_evidence_limit: int = 10
    judge_evidence_char_limit: int = 700
    # Model geçerli atıf üretemediğinde skora uygulanan tavan (kanıtsız yüksek puanı engeller).
    judge_uncited_score_cap: float = 65.0
    # Coverage: bir zorunlu konunun "semantik olarak mevcut" sayılması için gereken
    # minimum cosine benzerliği. similarity_score = 1 - cosine_distance (0-1).
    coverage_semantic_threshold: float = 0.55
    upload_session_timeout_seconds: int = 120
    allowed_origins: tuple[str, ...] = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    )
    allowed_origin_regex: str = r"https://[a-zA-Z0-9-]+\.trycloudflare\.com"


settings = Settings()
