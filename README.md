# tubitak-proposal-evaluator

## Makefile

Use these commands from the project root:

```bash
make setup
make warmup
make backend
make frontend
make run
make
```

Commands:

- `make setup`: creates the backend `.venv`, installs backend dependencies, and installs frontend packages.
- `make warmup`: downloads and caches the `BAAI/bge-m3` model before the first embedding run.
- `make backend`: starts the FastAPI backend service.
- `make frontend`: starts the Next.js frontend service.
- `make run`: starts backend and frontend together.
- `make`: runs `setup` first, then starts both services.

## Embedding Search

- The embedding pipeline runs after chunking inside the analysis flow.
- Embeddings are stored in a local Chroma persistence directory under `backend/runtime/embedding/chroma`.
- The embedding provider uses `BAAI/bge-m3` through the local `transformers` and `torch` stack.
- `make setup` installs the backend dependencies required by the embedding service, including `chromadb`, `torch`, and `transformers`.
- `make warmup` downloads the `BAAI/bge-m3` model into `backend/runtime/embedding/model-cache` before the first real analysis run.
- `make clean` removes `backend/runtime`, so local Chroma data is cleared as part of cleanup.
