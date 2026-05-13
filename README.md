# tubitak-proposal-evaluator

## Makefile

Use these commands from the project root:

```bash
make setup
make backend
make frontend
make run
make
```

Commands:

- `make setup`: creates the backend `.venv`, installs backend dependencies, and installs frontend packages.
- `make backend`: starts the FastAPI backend service.
- `make frontend`: starts the Next.js frontend service.
- `make run`: starts backend and frontend together.
- `make`: runs `setup` first, then starts both services.
