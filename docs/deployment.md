# Deployment

OmniRun has two deployables:

- `web/` — static React frontend. GitHub Pages hosts this.
- `api/` — FastAPI service. It needs a Python container host.

GitHub Pages cannot run the API. The public site stays in static preview mode until the frontend is pointed at a hosted API.

## Option A: Render (recommended)

The repository includes [`render.yaml`](../render.yaml) and a production [`Dockerfile`](../Dockerfile).

1. Sign in to [Render](https://render.com) with GitHub.
2. Choose **New → Blueprint**.
3. Select `Henok-Tekeba/omnirun`.
4. Apply the `omnirun-api` service. Render builds the Dockerfile and exposes a URL such as `https://omnirun-api.onrender.com`.
5. Copy the service URL.
6. In GitHub, open **Settings → Secrets and variables → Actions → Variables** and add:

   ```text
   VITE_API_BASE_URL=https://omnirun-api.onrender.com
   ```

7. Re-run **Deploy web to GitHub Pages** (or push to `main`).

   With the GitHub CLI:

   ```bash
   gh variable set VITE_API_BASE_URL \
     --repo Henok-Tekeba/omnirun \
     --body "https://your-service.onrender.com"

   gh workflow run deploy-pages.yml --repo Henok-Tekeba/omnirun
   ```

The Pages build will now call the hosted API. The static-preview banner disappears and live preflights, device discovery, and model search work.

### Render configuration

`render.yaml` sets:

| Variable | Value | Purpose |
| --- | --- | --- |
| `OMNIRUN_CORS_ORIGINS` | `https://henok-tekeba.github.io` | Allows the Pages origin |
| `OMNIRUN_CACHE_DIR` | `/tmp/omnirun-cache` | Ephemeral metadata cache |
| `OMNIRUN_TRUST_PROXY_HEADERS` | `true` | Rate-limit by real client IP behind Render's proxy |

Free Render services sleep after inactivity. The scheduled `keepalive.yml` workflow pings `/health` every 10 minutes when `VITE_API_BASE_URL` is configured. For production traffic, use a paid always-on instance.

## Option B: Docker anywhere

```bash
docker build -t omnirun-api .
docker run --rm -p 8000:8000 \
  -e OMNIRUN_CORS_ORIGINS=https://henok-tekeba.github.io \
  -e OMNIRUN_TRUST_PROXY_HEADERS=true \
  omnirun-api
```

Then set `VITE_API_BASE_URL` to the public HTTPS origin in front of the container.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `OMNIRUN_CORS_ORIGINS` | empty | Comma-separated allowed frontend origins |
| `OMNIRUN_TRUST_PROXY_HEADERS` | `false` | Enable only behind a trusted reverse proxy |
| `OMNIRUN_CACHE_DIR` | `~/.cache/omnirun` | Use an ephemeral path on hosts without persistent disks |
| `OMNIRUN_DATA_DIR` | repository `data/` | Device and support matrices |
| `OMNIRUN_RATE_LIMIT_PER_MINUTE` | `30` | Per-client IP limit |
| `OMNIRUN_RATE_LIMIT_BURST` | `10` | Token-bucket burst |
| `OMNIRUN_CHECK_TIMEOUT_SECONDS` | `30` | Whole-check deadline |
| `OMNIRUN_FIND_TIMEOUT_SECONDS` | `30` | Whole-finder deadline |

Do not set `OMNIRUN_TRUST_PROXY_HEADERS=true` unless the service is actually behind a proxy that overwrites `X-Forwarded-For`.

## Verify

```bash
curl -fsS https://your-api-host/health
curl -fsS https://your-api-host/devices | head
```

Then open the Pages site and run a preflight. Browser CORS failures usually mean `OMNIRUN_CORS_ORIGINS` does not exactly match the Pages origin.

## Frontend build variables

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | API origin, without `/api` |
| `VITE_BASE_PATH` | Pages subpath, e.g. `/omnirun/` |

See [`web/.env.example`](../web/.env.example).
