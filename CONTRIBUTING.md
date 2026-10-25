# Working on The Booth

## Setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn booth.api:app --reload --port 8000
```

The app runs without any keys (template crew). For the model-backed crew see [docs/FREE_SETUP.md](docs/FREE_SETUP.md).

## Workflow

1. Pick or open an issue and assign yourself.
2. Branch from `main`: `git switch -c <your-name>/<short-topic>`.
3. Before pushing:

   ```bash
   cd backend
   ruff format booth tests
   ruff check booth tests
   pytest -q
   ```

4. Open a pull request; CI (tests, lint, container build) must be green. One teammate reviews.

## Where things live

| Path | What |
|---|---|
| `backend/booth/sim/` | Synthetic match generator |
| `backend/booth/state.py`, `facts.py` | Shared match state and the stats desk (agent tools) |
| `backend/booth/agents/` | Director, stats producer, writers, fact-checker, localizer, templates |
| `backend/booth/crew.py`, `orchestrator.py` | Hand-offs per job; the live broadcast loop |
| `backend/booth/api.py` | HTTP API, rate limits, static frontend |
| `frontend/` | Web UI (no build step) |
| `infra/deploy.sh` | Azure setup |
| `docs/` | Architecture, deploy, free setup, pitch, demo script |

Never commit `.env` or keys. Push protection will block known key formats, but don't rely on it.
