# Phase 22 API Deployment

## Local run

```powershell
py -m uvicorn app:app --host 127.0.0.1 --port 8000
```

## Public deployment

Run behind a TLS-terminating reverse proxy and set `FPL_API_KEY` as a deployment secret. The `POST /api/run-pipeline` endpoint rejects requests without a matching `X-API-Key` header when the secret is configured. Do not expose the pipeline trigger directly to the public internet without this secret and network-level controls.

## API routes

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness and artifact availability. |
| GET | `/api/status` | Pipeline state and last successful run. |
| GET | `/api/summary` | Latest weekly summary with model and target metadata. |
| GET | `/api/players` | Current projected player/squad payload. |
| POST | `/api/run-pipeline` | Validated, concurrency-protected pipeline trigger. |
| GET | `/` | Dashboard UI. |

## Operational safeguards

Requests are validated with Pydantic constraints. Concurrent pipeline triggers receive HTTP 409. Pipeline failures are logged and returned as structured HTTP 500 errors. The API does not claim authentication unless `FPL_API_KEY` is configured.
