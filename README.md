# tubitak-proposal-evaluator

## Makefile

Use these commands from the project root:

```bash
make setup
make warmup
make backend
make frontend
make run
make check
make
```

Commands:

- `make setup`: creates the backend `.venv`, installs backend dependencies, installs frontend packages, and pulls the `aya-expanse:8b` Ollama model if it is not already available locally.
- `make warmup`: downloads and caches the `BAAI/bge-m3` model before the first embedding run.
- `make backend`: starts the FastAPI backend service.
- `make frontend`: starts the Next.js frontend service after clearing the local `.next` dev build cache.
- `make run`: starts backend and frontend together and clears the local `.next` dev build cache before boot.
- `make check`: verifies that service package `__init__.py` files are side-effect free and runs a backend import smoke test before runtime.
- `make`: runs `setup` first, then starts both services.

## Import Safety

- Service package `__init__.py` files under `backend/app/services/*` are intentionally kept side-effect free.
- The dev runner fails fast if one of those package entrypoints starts importing concrete service modules again.
- `make backend`, `make run`, `make warmup`, and `make check` all execute this guard before doing real work, so circular-import regressions are caught before the server boots.

## Embedding Search

- The embedding pipeline runs after chunking inside the analysis flow.
- Embeddings are stored in a local Chroma persistence directory under `backend/runtime/embedding/chroma`.
- The embedding provider uses `BAAI/bge-m3` through the local `transformers` and `torch` stack.
- `make setup` installs the backend dependencies required by the embedding service, including `chromadb`, `torch`, and `transformers`, and also prepares the local Ollama judge model.
- `make warmup` downloads the `BAAI/bge-m3` model into `backend/cache/embedding/model-cache` before the first real analysis run.
- `make clean` removes `backend/runtime`, so local Chroma data is cleared as part of cleanup, but the cached embedding model is preserved.

## Evaluation

- The evaluation pipeline runs after embeddings are ready and uses a separate evaluation state per session.
- Criterion scoring is evidence-backed: each criterion retrieves both supporting and contradicting chunks before sending them to the judge model.
- The local judge model is `aya-expanse:8b` served by `Ollama`.
- `make setup`, `make backend`, and `make run` expect `ollama` to be installed. If the Ollama server is not already running, the script starts it automatically and shuts it down again when the command exits.
