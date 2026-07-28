# Vercel Frontend Deployment

The repository contains a React/Vite frontend and a separate FastAPI/Celery backend. Vercel should build and host only the `frontend/` application. The backend must run at a public HTTPS URL on a separate service.

## Vercel Project Settings

Create a Vercel project from this repository and keep the project root at the repository root. The checked-in `vercel.json` already defines the frontend-only deployment:

| Setting | Value |
|---|---|
| Framework preset | Vite |
| Install command | `npm --prefix frontend ci` |
| Build command | `npm --prefix frontend run build` |
| Output directory | `frontend/dist` |

The `.vercelignore` file excludes the Python backend, benchmark data, model files, and local runtime assets from the Vercel upload.

## Required Environment Variable

Add this Production environment variable in Vercel:

```text
VITE_API_BASE_URL=https://your-public-backend.example.com
```

The value must be the public base URL of the FastAPI backend without a trailing slash. Do not use `127.0.0.1` or `localhost`; those addresses refer to the visitor's machine after deployment.

The frontend uses relative API paths during local development, where `frontend/vite.config.js` proxies requests to `http://127.0.0.1:8000`. On Vercel, `VITE_API_BASE_URL` converts API, preview, result-video, and live-stream URLs to the remote backend origin at build time.

## Backend CORS

Add the deployed Vercel origin to the backend's `CORS_ORIGINS` variable. Include preview and production origins when needed:

```text
CORS_ORIGINS=https://your-project.vercel.app,https://your-custom-domain.example.com
```

The backend must also expose its API, static/result URLs, and live-stream endpoints over HTTPS. A local backend cannot be reached by a deployed Vercel frontend.

## Deploy with the CLI

From the repository root:

```bash
npm install -g vercel
vercel login
vercel
vercel --prod
```

When prompted, link the project to the current repository. The existing `vercel.json` supplies the build and output settings.

## Smoke Test After Deployment

1. Open the deployed URL and confirm the React application loads.
2. Upload a small supported video and verify the request reaches the public backend.
3. Confirm the preview image, task progress, result video, and JSON result load from the backend origin.
4. Test a live source only after batch upload works.

If the UI loads but requests fail, inspect the browser Network tab first. A CORS error means the backend origin is missing from `CORS_ORIGINS`; a `VITE_API_BASE_URL` error means the Vercel environment variable was not configured before the build.
