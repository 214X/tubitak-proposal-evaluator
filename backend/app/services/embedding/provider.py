from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from fastapi import HTTPException, status
import torch
from transformers import AutoModel, AutoTokenizer

from app.core.config import settings
from app.services.embedding.models import EmbeddingProviderName

MODEL_LOCK = Lock()
TOKENIZER_INSTANCE = None
MODEL_INSTANCE = None


@dataclass(frozen=True)
class EmbeddingProvider:
    name: EmbeddingProviderName
    model_name: str
    tokenizer: AutoTokenizer
    model: AutoModel

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        vectors: list[list[float]] = []
        for batch_start in range(0, len(texts), 8):
            batch = texts[batch_start : batch_start + 8]
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=settings.embedding_model_max_length,
                return_tensors="pt",
            )
            with torch.no_grad():
                outputs = self.model(**encoded)

            pooled = _mean_pool(
                outputs.last_hidden_state,
                encoded["attention_mask"],
            )
            normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vectors.extend(normalized.cpu().tolist())

        return vectors

    @property
    def dimensions(self) -> int:
        return int(self.model.config.hidden_size)


def get_embedding_provider(provider_name: EmbeddingProviderName | None = None) -> EmbeddingProvider:
    normalized_provider_name = provider_name or "bge_m3"
    if normalized_provider_name != "bge_m3":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported embedding provider: {normalized_provider_name}",
        )

    return EmbeddingProvider(
        name="bge_m3",
        model_name=settings.embedding_model_name,
        tokenizer=_get_tokenizer(),
        model=_get_model(),
    )


def _get_tokenizer():
    global TOKENIZER_INSTANCE
    if TOKENIZER_INSTANCE is not None:
        return TOKENIZER_INSTANCE

    with MODEL_LOCK:
        if TOKENIZER_INSTANCE is not None:
            return TOKENIZER_INSTANCE

        cache_dir = Path(__file__).resolve().parents[3] / settings.embedding_model_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        TOKENIZER_INSTANCE = AutoTokenizer.from_pretrained(
            settings.embedding_model_name,
            cache_dir=str(cache_dir),
            trust_remote_code=True,
        )
        return TOKENIZER_INSTANCE


def _get_model():
    global MODEL_INSTANCE
    if MODEL_INSTANCE is not None:
        return MODEL_INSTANCE

    with MODEL_LOCK:
        if MODEL_INSTANCE is not None:
            return MODEL_INSTANCE

        cache_dir = Path(__file__).resolve().parents[3] / settings.embedding_model_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        MODEL_INSTANCE = AutoModel.from_pretrained(
            settings.embedding_model_name,
            cache_dir=str(cache_dir),
            trust_remote_code=True,
        )
        MODEL_INSTANCE.eval()
        return MODEL_INSTANCE


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    sum_embeddings = torch.sum(last_hidden_state * mask, dim=1)
    sum_mask = torch.clamp(mask.sum(dim=1), min=1e-9)
    return sum_embeddings / sum_mask
